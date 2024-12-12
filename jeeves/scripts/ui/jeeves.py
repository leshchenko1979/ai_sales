"""Main Jeeves UI module."""

import asyncio
import logging
import sys

import questionary
from core import db
from core.accounts import queries as account_queries
from core.campaigns import queries as campaign_queries
from core.companies import queries as company_queries
from infrastructure.logging import setup_logging

from .campaign.audiences import AudienceUI
from .campaign.campaigns import CampaignUI
from .campaign.companies import CompanyUI
from .styles import STYLE

# Configure logging but suppress output
setup_logging()
logging.getLogger().handlers.clear()  # Remove any existing handlers
null_handler = logging.NullHandler()
logging.getLogger().addHandler(null_handler)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # Only show warnings and above


class JeevesUI:
    """Main Jeeves interface."""

    def __init__(self) -> None:
        """Initialize Jeeves UI."""
        logger.debug("Initializing JeevesUI")
        self.separator_length = 50
        self.campaign_ui = CampaignUI(self)
        self.company_ui = CompanyUI(self)
        self.audience_ui = AudienceUI(self)
        logger.info("JeevesUI initialized successfully")

    def print_separator(self) -> None:
        """Print separator line."""
        print("-" * self.separator_length)

    async def run(self) -> None:
        """Run the Jeeves interface."""
        logger.info("Starting JeevesUI.run()")
        try:
            while True:
                try:
                    logger.debug("Displaying main menu")
                    print("\nMain Menu")
                    self.print_separator()

                    logger.debug("Waiting for user selection")
                    choice = await self._get_menu_choice()
                    logger.info(f"User selected menu option: {choice}")

                    if choice == 0:
                        await self._handle_exit()
                    elif choice == 1:
                        await self._handle_campaigns()
                    elif choice == 2:
                        await self._handle_companies()

                except SystemExit:
                    logger.debug("SystemExit caught in main loop")
                    raise
                except Exception as e:
                    logger.error(f"Error in main loop: {e}", exc_info=True)
                    self._handle_error(e)
                    await self._pause()

        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Received interrupt signal")
            print("\nShutting down gracefully...")
            logger.debug("Raising SystemExit from interrupt handler")
            await self.cleanup()
            raise SystemExit
        except SystemExit:
            logger.info("Exiting cleanly")
            print("User selected Exit")
            logger.debug("Final cleanup before exit")
            await self.cleanup()
            raise
        finally:
            logger.info("JeevesUI shutdown complete")

    async def _get_menu_choice(self) -> int:
        """Get user's menu choice."""
        return await questionary.select(
            "Select action:",
            choices=[
                questionary.Choice("Campaigns", 1),
                questionary.Choice("Companies", 2),
                questionary.Choice("Exit", 0),
            ],
            style=STYLE,
        ).ask_async()

    async def _handle_exit(self) -> None:
        """Handle exit selection."""
        logger.info("User selected Exit")
        print("\nExiting Jeeves...")
        logger.debug("Initiating clean shutdown")
        await self.cleanup()
        sys.exit(0)

    async def _handle_campaigns(self) -> None:
        """Handle campaigns menu selection."""
        logger.info("Starting campaign management")
        await self.manage_campaigns()
        logger.debug("Returned from campaign management")

    async def _handle_companies(self) -> None:
        """Handle companies menu selection."""
        logger.info("Starting company management")
        await self.manage_companies()
        logger.debug("Returned from company management")

    async def cleanup(self) -> None:
        """Perform cleanup operations before exit."""
        logger.debug("Running cleanup operations")
        # Add any cleanup operations here
        await asyncio.sleep(0)  # Yield control to ensure async operations complete

    def _handle_error(self, error: Exception) -> None:
        """Handle and display error information."""
        logger.error(f"Error handler called: {error}", exc_info=True)
        print("\nError occurred: ", str(error))
        print("\nFull error details:")
        import traceback

        print(traceback.format_exc())

    async def _pause(self) -> None:
        """Pause execution until user presses Enter."""
        logger.debug("Pausing for user input")
        input("Press Enter to continue...")
        logger.debug("User pressed Enter to continue")

    @db.with_queries((campaign_queries.CampaignQueries, account_queries.AccountQueries))
    async def manage_campaigns(
        self,
        campaign_queries: campaign_queries.CampaignQueries,
        account_queries: account_queries.AccountQueries,
    ) -> None:
        """Manage campaigns submenu."""
        while True:
            try:
                print("\nCampaign Management")
                self.print_separator()

                choice = await questionary.select(
                    "Select action:",
                    choices=[
                        questionary.Choice("View Campaigns", 1),
                        questionary.Choice("Create Campaign", 2),
                        questionary.Choice("Quick Actions", 3),
                        questionary.Choice("Back to Main Menu", 0),
                    ],
                    style=STYLE,
                ).ask_async()

                if choice == 0:
                    break
                elif choice == 1:
                    await self.campaign_ui.view_campaigns()
                elif choice == 2:
                    await self.campaign_ui.create_campaign()
                elif choice == 3:
                    await self.campaign_ui.campaign_quick_actions()

            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\nReturning to main menu...")
                break

    @db.with_queries(company_queries.CompanyQueries)
    async def manage_companies(self, queries: company_queries.CompanyQueries):
        """Handle company management menu."""
        while True:
            print("\nCompany Management")
            self.print_separator()

            action = await questionary.select(
                "Select action:",
                choices=[
                    questionary.Choice("View Companies", "view"),
                    questionary.Choice("Create Company", "create"),
                    questionary.Choice("Back", "back"),
                ],
                style=STYLE,
            ).ask_async()

            if action == "back":
                return  # Return without pause when going back
            elif action == "view":
                await self.company_ui.view_companies()
            elif action == "create":
                await self.company_ui.create_company()

            # Only pause after create, not after view or back
            if action == "create":
                await self._pause()
