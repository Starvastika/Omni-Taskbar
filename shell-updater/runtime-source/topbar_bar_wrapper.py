"""Narrow delegates around the ORIGINAL CURRENT installed Bar code object."""
exec('__YASB_CURRENT_BAR_CODE__', globals())

_hover_original_update_app_bar = Bar.update_app_bar
_hover_original_position_bar = Bar.position_bar


def _hover_update_app_bar(self):
    policy = getattr(self, '_maximized_watcher', None)
    if getattr(policy, 'managed_appbar', False):
        policy.refresh_appbar()
    else:
        _hover_original_update_app_bar(self)


def _hover_position_bar(self, init=False):
    policy = getattr(self, '_maximized_watcher', None)
    if getattr(policy, 'managed_appbar', False) and policy.position_bar():
        return
    _hover_original_position_bar(self, init)


Bar.update_app_bar = _hover_update_app_bar
Bar.position_bar = _hover_position_bar
