"""Only these two methods replace their installed code objects.

All other listener bytecode stays exactly as installed, including shutdown.
Location notifications were deliberately absent in this installed build.
The added hook delivers only actual top-level window geometry changes.
"""
def _build_event_hooks(self):
    skipped = WinEvent.EventObjectLocationChange.value
    hooks = [self._hook_range(WinEvent.EventMin.value, skipped-1),
             self._hook_range(skipped+1, WinEvent.EventObjectEnd.value),
             self._hook_range(skipped, skipped)]
    if not all(hooks):
        for hook in hooks:
            if hook:
                user32.UnhookWinEvent(hook)
        return []
    return hooks


def _event_handler(self, hook, event, hwnd, object_id, child_id, thread_id, timestamp):
    if event == WinEvent.EventObjectLocationChange.value:
        # OBJID_WINDOW = 0. Discard caret/client/scroll/content-object churn.
        if object_id != 0 or child_id != 0:
            return
    if event in WinEvent:
        event_type = WinEvent._value2member_map_[event]
        try:
            self._event_service.emit_event(event_type, hwnd, event_type)
            if (event in (3,10,11,21,22,23,32769,32770,32771,32779,32791,32792)
                    and (event < 32768 or (object_id == 0 and child_id == 0))):
                self._event_service.emit_event('topbar_window_state', hwnd, event_type)
        except Exception:
            logging.exception('Failed to emit event %s for %s', event_type, hwnd)
