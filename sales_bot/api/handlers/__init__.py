"""Command handlers package."""

from .common import cmd_help, cmd_start
from .testing import cmd_stop_dialog, cmd_test_dialog, on_test_message

__all__ = [
    "cmd_help",
    "cmd_start",
    "cmd_test_dialog",
    "cmd_stop_dialog",
    "on_test_message",
]

# Store original handlers for future reference
ORIGINAL_HANDLERS = {
    # Account commands
    "cmd_add_account": "from .accounts import cmd_add_account",
    "cmd_authorize": "from .accounts import cmd_authorize",
    "cmd_check_account": "from .accounts import cmd_check_account",
    "cmd_check_all_accounts": "from .accounts import cmd_check_all_accounts",
    "cmd_list_accounts": "from .accounts import cmd_list_accounts",
    "cmd_resend_code": "from .accounts import cmd_resend_code",
    # Dialog commands
    "cmd_export_all_dialogs": "from .dialogs import cmd_export_all_dialogs",
    "cmd_export_dialog": "from .dialogs import cmd_export_dialog",
    "cmd_start_dialog": "from .dialogs import cmd_start_dialog",
}
