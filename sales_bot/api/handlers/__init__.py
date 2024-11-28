"""Command handlers package."""

from .accounts import (
    cmd_add_account,
    cmd_authorize,
    cmd_check_account,
    cmd_check_all_accounts,
    cmd_list_accounts,
    cmd_resend_code,
)
from .common import admin, cmd_help
from .dialogs import cmd_export_all_dialogs, cmd_export_dialog, cmd_start_dialog
from .testing import cmd_test_dialog

__all__ = [
    # Account commands
    "cmd_add_account",
    "cmd_authorize",
    "cmd_check_account",
    "cmd_check_all_accounts",
    "cmd_list_accounts",
    "cmd_resend_code",
    # Dialog commands
    "cmd_export_all_dialogs",
    "cmd_export_dialog",
    "cmd_start_dialog",
    # Testing commands
    "cmd_test_dialog",
    # Common
    "cmd_help",
    "admin",
]
