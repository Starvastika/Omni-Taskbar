"""One bounded, disposable semantic provider request. No GUI or input synthesis.

The parent kills this process on timeout/cancellation. COM references and raw
menu handles never leave a request except as revalidated identity metadata.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import sys
import time

U = C.WinDLL('user32', use_last_error=True)
def api(name, result, *args):
    f = getattr(U, name); f.restype = result; f.argtypes = args; return f
is_window = api('IsWindow', W.BOOL, W.HWND)
get_menu = api('GetMenu', W.HMENU, W.HWND)
menu_count = api('GetMenuItemCount', C.c_int, W.HMENU)
get_pid = api('GetWindowThreadProcessId', W.DWORD, W.HWND, C.POINTER(W.DWORD))
foreground = api('GetForegroundWindow', W.HWND)
ancestor = api('GetAncestor', W.HWND, W.HWND, W.UINT)
send = api('SendMessageTimeoutW', C.c_size_t, W.HWND, W.UINT, C.c_size_t, C.c_ssize_t, W.UINT, W.UINT, C.POINTER(C.c_size_t))

class MenuItem(C.Structure):
    _fields_ = [('cbSize',W.UINT),('fMask',W.UINT),('fType',W.UINT),('fState',W.UINT),('wID',W.UINT),
                ('hSubMenu',W.HMENU),('hbmpChecked',W.HBITMAP),('hbmpUnchecked',W.HBITMAP),
                ('dwItemData',C.c_size_t),('dwTypeData',W.LPWSTR),('cch',W.UINT),('hbmpItem',W.HBITMAP)]
class MenuInfo(C.Structure):
    _fields_=[('cbSize',W.DWORD),('fMask',W.DWORD),('dwStyle',W.DWORD),('cyMax',W.UINT),
              ('hbrBack',W.HBRUSH),('dwContextHelpID',W.DWORD),('dwMenuData',C.c_size_t)]
get_item = api('GetMenuItemInfoW',W.BOOL,W.HMENU,W.UINT,W.BOOL,C.POINTER(MenuItem))
get_info = api('GetMenuInfo',W.BOOL,W.HMENU,C.POINTER(MenuInfo))

def pid(hwnd):
    value=W.DWORD();get_pid(hwnd,C.byref(value));return value.value

def valid(request, interaction=False):
    h=request['hwnd']
    if not is_window(h) or pid(h)!=request['pid']:
        raise ValueError('target destroyed or replaced')
    if interaction:
        fg=foreground()
        if fg and pid(fg)!=request.get('shell_pid') and ancestor(fg,3)!=ancestor(h,3):
            # UIA can expose a target-owned popup as a separate HWND. Accept
            # only actual menu surfaces of that PID, not another main window.
            buf=C.create_unicode_buffer(128)
            api('GetClassNameW',C.c_int,W.HWND,W.LPWSTR,C.c_int)(fg,buf,128)
            if pid(fg)!=request['pid'] or buf.value!='#32768':
                raise ValueError('foreground target changed')

def message(request,msg,wparam=0,lparam=0):
    valid(request,True)
    result=C.c_size_t()
    if not send(request['hwnd'],msg,wparam,lparam,0x2|0x20,120,C.byref(result)):
        raise TimeoutError('native target did not complete the request')

def dispatch(request,msg,wparam,lparam):
    # Commands may synchronously enter a modal message loop (e.g. About).
    # Queue the validated native menu notification once; never wait for the
    # application's command handler to finish and never retry delivery.
    valid(request,True)
    if not api('PostMessageW',W.BOOL,W.HWND,W.UINT,C.c_size_t,C.c_ssize_t)(request['hwnd'],msg,wparam,lparam):
        raise OSError('native command could not be queued')

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def label(text):
    # Preserve localized spelling; remove Win32 mnemonic markup only.
    title,*shortcut=text.split('\t',1)
    return title.replace('&&','\0').replace('&','').replace('\0','&').strip(), shortcut[0] if shortcut else ''

def structure(nodes):
    return [(n['kind'],n['label'],n.get('selector'),structure(n.get('children',[]))) for n in nodes]

def native(request):
    root=int(get_menu(request['hwnd']) or 0)
    if not root:return None
    if request.get('root') and request['root']!=root:raise ValueError('native menu replaced')
    total=[0]; deadline=time.monotonic()+1.0
    def item(menu,index):
        text=C.create_unicode_buffer(2048)
        info=MenuItem();info.cbSize=C.sizeof(info);info.fMask=0x1|0x2|0x4|0x40|0x100
        info.dwTypeData=C.cast(text,W.LPWSTR);info.cch=2047
        if not get_item(menu,index,True,C.byref(info)):raise ValueError('native item unavailable')
        return info,text.value
    if request['op'] in ('refresh','invoke'):
        message(request,0x116,root,0)  # WM_INITMENU, never a keyboard sequence
        menu=root
        for index in request.get('route',[]):
            info,_=item(menu,index)
            if not info.hSubMenu:break
            menu=int(info.hSubMenu)
            message(request,0x117,menu,index)  # WM_INITMENUPOPUP, normal menu
    def read(menu,route,path,depth=0):
        if depth>7:return []
        count=menu_count(menu)
        if count<0:raise ValueError('native menu expired')
        nodes=[]
        for index in range(min(count,150)):
            if total[0]>=600 or time.monotonic()>deadline:break
            total[0]+=1
            info,text=item(menu,index)
            title,shortcut=label(text)
            r=route+[index];p=path+[title]
            kind='separator' if info.fType&0x800 else 'submenu' if info.hSubMenu else 'command'
            node=dict(provider='hmenu',kind=kind,label=title,path=p,shortcut=shortcut,
                      enabled=not bool(info.fState&3),checked=bool(info.fState&8),radio=bool(info.fType&0x200),
                      has_submenu=bool(info.hSubMenu),selector={'route':r,'id':info.wID},dynamic=True,confidence='native')
            node['key']=digest(('hmenu',root,r,info.wID,title))
            node['children']=read(int(info.hSubMenu),r,p,depth+1) if info.hSubMenu else []
            # Opaque owner-drawn headings/commands are not synthesized.
            if title or kind=='separator':nodes.append(node)
        return nodes
    nodes=read(root,[],[])
    signature=digest((root,structure(nodes)))
    model=dict(provider='hmenu',menus=nodes,signature=signature,root=root,partial=total[0]>=600)
    if request['op']=='invoke':
        if request.get('signature')!=signature:raise ValueError('native structure changed; refresh required')
        selected=None
        def find(items):
            nonlocal selected
            for n in items:
                if n['key']==request['command']['key']:selected=n
                find(n['children'])
        find(nodes)
        if not selected or selected['kind']!='command' or not selected['enabled']:
            raise ValueError('command missing, disabled or not actionable')
        menu=root
        for index in selected['selector']['route'][:-1]:
            info,_=item(menu,index);menu=int(info.hSubMenu or 0)
            if not menu:raise ValueError('submenu replaced')
        index=selected['selector']['route'][-1]
        info=MenuInfo();info.cbSize=C.sizeof(info);info.fMask=0x10
        if not get_info(menu,C.byref(info)):raise ValueError('menu semantics unavailable')
        if info.dwStyle&0x08000000:
            dispatch(request,0x126,index,menu)  # MNS_NOTIFYBYPOS -> WM_MENUCOMMAND
        else:
            command_id=selected['selector']['id']
            if not 0<command_id<=0xffff:raise ValueError('command ID is not representable by WM_COMMAND')
            dispatch(request,0x111,command_id,0)
        model['invoked']=True
    return model

def automation(request):
    # This entire COM apartment exists only in the disposable worker process.
    sys.coinit_flags=0  # MTA
    sys.path.insert(0,str(Path(__file__).parent/'vendor'))
    import comtypes.client
    from comtypes.gen import UIAutomationClient as A
    uia=comtypes.client.CreateObject(A.CUIAutomation,interface=A.IUIAutomation)
    root=uia.ElementFromHandle(request['hwnd']);walker=uia.ControlViewWalker
    deadline=time.monotonic()+1.1; budget=[0];expanded=[]
    def pattern(el,number,interface):
        try:return el.GetCurrentPattern(number).QueryInterface(interface)
        except Exception:return None
    def selector(el):
        return {'rid':list(el.GetRuntimeId()),'name':el.CurrentName or '',
                'aid':el.CurrentAutomationId or '', 'type':el.CurrentControlType}
    def children(el):
        result=[];child=walker.GetFirstChildElement(el)
        while child:
            budget[0]+=1
            if budget[0]>300 or time.monotonic()>deadline:break
            result.append(child);child=walker.GetNextSiblingElement(child)
        return result
    def node(el,path,route,depth=0):
        s=selector(el);name=s['name'];route=route+[s]
        expand=pattern(el,A.UIA_ExpandCollapsePatternId,A.IUIAutomationExpandCollapsePattern)
        invoke=pattern(el,A.UIA_InvokePatternId,A.IUIAutomationInvokePattern)
        toggle=pattern(el,A.UIA_TogglePatternId,A.IUIAutomationTogglePattern)
        select=pattern(el,A.UIA_SelectionItemPatternId,A.IUIAutomationSelectionItemPattern)
        kid=[]
        if depth<6:
            for child in children(el):
                kind=child.CurrentControlType
                if kind in (A.UIA_MenuItemControlTypeId,A.UIA_SeparatorControlTypeId):kid.append(node(child,path+[name],route,depth+1))
                elif kind==A.UIA_MenuControlTypeId:
                    for leaf in children(child):
                        if leaf.CurrentControlType in (A.UIA_MenuItemControlTypeId,A.UIA_SeparatorControlTypeId):kid.append(node(leaf,path+[name],route,depth+1))
        submenu=bool(expand and expand.CurrentExpandCollapseState!=3) or bool(kid)
        method='invoke' if invoke else 'toggle' if toggle else 'select' if select else None
        checked=bool(toggle.CurrentToggleState==1) if toggle else bool(select.CurrentIsSelected) if select else False
        if not toggle and not select:
            legacy=pattern(el,A.UIA_LegacyIAccessiblePatternId,A.IUIAutomationLegacyIAccessiblePattern)
            if legacy:checked=bool(legacy.CurrentState&0x10)
        result=dict(provider='uia',label=name,path=path+[name],kind='separator' if s['type']==A.UIA_SeparatorControlTypeId else 'submenu' if submenu else 'command',
                    shortcut=el.CurrentAcceleratorKey or '',enabled=bool(el.CurrentIsEnabled) and bool(submenu or method),
                    checked=checked,radio=bool(select),has_submenu=submenu,selector={'route':route},
                    method=method,dynamic=True,confidence='semantic-pattern',children=kid)
        result['key']=digest(('uia',request['hwnd'],route))
        return result
    def bars():
        result=[]
        # Bounded structural walk. Prune document/editor/list content, never
        # scrape arbitrary buttons or every element in a web page/ribbon.
        containers={A.UIA_WindowControlTypeId,A.UIA_PaneControlTypeId,A.UIA_GroupControlTypeId,A.UIA_CustomControlTypeId,A.UIA_ToolBarControlTypeId}
        def walk(el,depth):
            if depth>6 or budget[0]>180 or time.monotonic()>deadline:return
            for child in children(el):
                t=child.CurrentControlType
                if t in (A.UIA_MenuBarControlTypeId,A.UIA_MenuControlTypeId):
                    for heading in children(child):
                        if heading.CurrentControlType==A.UIA_MenuItemControlTypeId:result.append(heading)
                elif t==A.UIA_ToolBarControlTypeId:
                    for heading in children(child):
                        typ=heading.CurrentControlType
                        p=pattern(heading,A.UIA_ExpandCollapsePatternId,A.IUIAutomationExpandCollapsePattern)
                        if typ==A.UIA_MenuItemControlTypeId or typ==A.UIA_ButtonControlTypeId and p and p.CurrentExpandCollapseState!=3:
                            result.append(heading)
                    walk(child,depth+1)
                elif t in containers:walk(child,depth+1)
        walk(root,0)
        return result
    headings=bars()
    def match(candidates,s):
        exact=[e for e in candidates if list(e.GetRuntimeId())==s['rid']]
        if len(exact)==1:
            e=exact[0]
            if e.CurrentControlType!=s['type'] or e.CurrentName!=s['name'] or s['aid'] and e.CurrentAutomationId!=s['aid']:
                raise ValueError('UIA runtime identity now describes a different command')
            return e
        # Reopened UIA popup RIDs can change. Require a UNIQUE semantic identity
        # under the already validated parent; never rely on ordinal/menu order.
        matches=[e for e in candidates if e.CurrentControlType==s['type'] and e.CurrentName==s['name']
                 and (not s['aid'] or e.CurrentAutomationId==s['aid'])]
        if len(matches)!=1:raise ValueError('UIA element changed or ambiguous')
        return matches[0]
    def menu_children(el):
        result=[]
        for child in children(el):
            if child.CurrentControlType==A.UIA_MenuItemControlTypeId:result.append(child)
            elif child.CurrentControlType==A.UIA_MenuControlTypeId:result.extend(children(child))
        if not result:
            # Only target-process desktop-level popup Menu surfaces; no global
            # descendant crawl, and no coordinate/focus/keyboard simulation.
            condition=uia.CreateAndCondition(uia.CreatePropertyCondition(A.UIA_ProcessIdPropertyId,request['pid']),
                                             uia.CreatePropertyCondition(A.UIA_ControlTypePropertyId,A.UIA_MenuControlTypeId))
            popups=uia.GetRootElement().FindAll(A.TreeScope_Children,condition)
            if popups.Length==1:result=children(popups.GetElement(0))
        return [e for e in result if e.CurrentControlType in (A.UIA_MenuItemControlTypeId,A.UIA_SeparatorControlTypeId)]
    def expand(el):
        valid(request,True)
        p=pattern(el,A.UIA_ExpandCollapsePatternId,A.IUIAutomationExpandCollapsePattern)
        if not p:raise ValueError('no supported submenu expansion pattern')
        if p.CurrentExpandCollapseState==0:
            p.Expand();expanded.append(p)
    def ready_children(el):
        # ExpandCollapse can return before another GUI thread materializes its
        # popup. A short request-local wait handles that race off the YASB
        # thread; it is not an idle or whole-tree polling loop.
        until=min(deadline,time.monotonic()+.12)
        result=menu_children(el)
        while not result and time.monotonic()<until and budget[0]<280:
            time.sleep(.012);valid(request,True);result=menu_children(el)
        return result
    try:
        target=None
        route=request.get('command',{}).get('selector',{}).get('route',request.get('selector',{}).get('route',[]))
        if request['op'] in ('refresh','invoke') and route:
            candidates=headings
            for i,s in enumerate(route):
                target=match(candidates,s)
                if i<len(route)-1:
                    expand(target);candidates=ready_children(target)
            if request['op']=='refresh':
                expand(target)
                available=ready_children(target)
                refreshed=node(target,request.get('path',[])[:-1],route[:-1])
                refreshed['children']=[node(e,request.get('path',[]),route) for e in available]
                return dict(provider='uia',subtree=refreshed,partial=True)
            valid(request,True)
            if not target.CurrentIsEnabled:raise ValueError('command disabled')
            method=request['command'].get('method')
            p=pattern(target,{'invoke':A.UIA_InvokePatternId,'toggle':A.UIA_TogglePatternId,'select':A.UIA_SelectionItemPatternId}.get(method,0),
                      {'invoke':A.IUIAutomationInvokePattern,'toggle':A.IUIAutomationTogglePattern,'select':A.IUIAutomationSelectionItemPattern}.get(method,A.IUIAutomationInvokePattern))
            if not p:raise ValueError('command pattern no longer supported')
            {'invoke':lambda:p.Invoke(),'toggle':lambda:p.Toggle(),'select':lambda:p.Select()}[method]()
            return dict(provider='uia',invoked=True)
        nodes=[node(e,[],[]) for e in headings if e.CurrentName]
        return dict(provider='uia' if nodes else 'fallback',menus=nodes,signature=digest(structure(nodes)),partial=True)
    finally:
        for p in reversed(expanded):
            try:p.Collapse()
            except Exception:pass

def run(request):
    valid(request)
    start=time.perf_counter()
    if request.get('provider')=='uia':result=automation(request)
    else:
        result=native(request)
        if result is None and request.get('provider')=='hmenu':raise ValueError('native menu no longer attached')
        if result is None or not result['menus']:
            result=automation(request)
    result.update(ok=True,elapsed_ms=(time.perf_counter()-start)*1000)
    return result

if __name__=='__main__':
    try:
        request=json.loads(sys.stdin.read(131072))
        result=run(request)
    except Exception as exc:
        result=dict(ok=False,error=f'{type(exc).__name__}: {exc}')
    sys.stdout.write(json.dumps(result,ensure_ascii=True));sys.stdout.flush()
