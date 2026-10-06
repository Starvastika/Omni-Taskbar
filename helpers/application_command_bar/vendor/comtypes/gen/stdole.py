from enum import IntFlag

import comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 as __wrapper_module__
from comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 import (
    EXCEPINFO, VgaColor, IPictureDisp, OLE_ENABLEDEFAULTBOOL, Font,
    IFontEventsDisp, FONTBOLD, DISPMETHOD, COMMETHOD, GUID,
    OLE_YPOS_CONTAINER, OLE_CANCELBOOL, OLE_XPOS_PIXELS,
    OLE_XSIZE_PIXELS, VARIANT_BOOL, Picture, DISPPARAMS, Checked,
    OLE_XSIZE_CONTAINER, OLE_COLOR, Library, IFont, IUnknown,
    IFontDisp, CoClass, DISPPROPERTY, IDispatch, OLE_XPOS_CONTAINER,
    FONTSIZE, StdFont, OLE_YPOS_HIMETRIC, OLE_YSIZE_HIMETRIC,
    IPicture, Gray, OLE_XPOS_HIMETRIC, FontEvents, HRESULT,
    FONTSTRIKETHROUGH, _check_version, OLE_XSIZE_HIMETRIC, Unchecked,
    OLE_OPTEXCLUSIVE, dispid, OLE_YPOS_PIXELS, Monochrome, FONTNAME,
    FONTUNDERSCORE, typelib_path, Default, Color, OLE_YSIZE_PIXELS,
    IEnumVARIANT, BSTR, StdPicture, OLE_YSIZE_CONTAINER, OLE_HANDLE,
    _lcid, FONTITALIC
)


class OLE_TRISTATE(IntFlag):
    Unchecked = 0
    Checked = 1
    Gray = 2


class LoadPictureConstants(IntFlag):
    Default = 0
    Monochrome = 1
    VgaColor = 2
    Color = 4


__all__ = [
    'LoadPictureConstants', 'OLE_YPOS_HIMETRIC', 'VgaColor',
    'OLE_YSIZE_HIMETRIC', 'IPicture', 'Gray', 'IPictureDisp',
    'OLE_XPOS_HIMETRIC', 'FontEvents', 'OLE_ENABLEDEFAULTBOOL',
    'Font', 'FONTSTRIKETHROUGH', 'IFontEventsDisp', 'FONTBOLD',
    'OLE_XSIZE_HIMETRIC', 'Unchecked', 'OLE_OPTEXCLUSIVE',
    'OLE_YPOS_PIXELS', 'OLE_YPOS_CONTAINER', 'OLE_CANCELBOOL',
    'OLE_XPOS_PIXELS', 'Monochrome', 'FONTNAME', 'OLE_XSIZE_PIXELS',
    'FONTUNDERSCORE', 'typelib_path', 'Picture', 'Default',
    'OLE_YSIZE_PIXELS', 'Color', 'Checked', 'OLE_XSIZE_CONTAINER',
    'OLE_TRISTATE', 'OLE_COLOR', 'Library', 'IFont', 'StdPicture',
    'OLE_YSIZE_CONTAINER', 'OLE_HANDLE', 'IFontDisp', 'FONTITALIC',
    'OLE_XPOS_CONTAINER', 'FONTSIZE', 'StdFont'
]

