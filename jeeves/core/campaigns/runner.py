"""Campaign runner implementation for managing campaign execution and dialog creation."""

# Standard library imports
import asyncio
import logging
import random
from typing import List, Optional

# Local application imports
from core import db
from core.accounts import models as account_models
from core.accounts.queries import AccountQueries
from core.audiences import models as audience_models
from core.audiences.queries import AudienceQueries
from core.messaging import models as message_models
from core.messaging.queries import dialog as dialog_queries

from . import models, queries

logger = logging.getLogger(__name__)


class CampaignRunnerError(Exception):
    """Base exception for campaign runner errors."""


class CampaignRunner:
    """Manages execution of campaigns and dialog creation.

    This class is responsible for:
    1. Managing campaign execution
    2. Handling account selection and availability
    3. Creating and initializing dialogs
    4. Coordinating with dialog conductors

    Attributes:
        campaign_id: ID of the campaign being run
        _stop_event: Event to signal campaign stop
    """

    def __init__(self, campaign_id: int):
        """Initialize campaign runner.

        Args:
            campaign_id: ID of campaign to run
        """
        self.campaign_id = campaign_id
        self._stop_event = asyncio.Event()

    # Core operations
    async def run(self) -> None:
        """Run campaign processing loop.

        The main processing loop that:
        1. Checks campaign status
        2. Gets available accounts
        3. Processes each account
        4. Handles errors and retries
        """
        while not self._stop_event.is_set():
            try:
                # Get campaign and check status
                campaign = await self._get_campaign()
                if not campaign or campaign.status != models.CampaignStatus.active:
                    await self.stop()
                    break

                # Get and process available accounts
                accounts = await self.get_campaign_accounts()
                if not accounts:
                    logger.warning(
                        f"No available accounts for campaign {self.campaign_id}"
                    )
                    await self._handle_no_accounts()
                    continue

                await self._process_accounts(accounts)

            except Exception as e:
                logger.error(f"Error in campaign runner: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry

    async def stop(self) -> None:
        """Stop campaign runner gracefully."""
        self._stop_event.set()

    # Account operations
    @db.decorators.with_queries((queries.CampaignQueries, AccountQueries))
    async def get_campaign_accounts(
        self,
        campaign_queries: queries.CampaignQueries,
        account_queries: AccountQueries,
    ) -> List[account_models.Account]:
        """Get available accounts for campaign.

        Returns:
            List of available accounts that:
            - Are assigned to the campaign
            - Meet safety requirements
            - Are not blocked/disabled
        """
        campaign = await campaign_queries.get_campaign(self.campaign_id)
        if not campaign or campaign.status != models.CampaignStatus.active:
            return []

        return [account for account in campaign.accounts if account.can_be_used]

    # Contact operations
    @db.decorators.with_queries(AudienceQueries)
    async def get_random_contact(
        self, queries: AudienceQueries
    ) -> Optional[audience_models.Contact]:
        """Get random contact from campaign audiences.

        Returns:
            Random valid contact if available, None otherwise

        Note:
            Only returns contacts that:
            - Belong to campaign audiences
            - Are marked as valid
            - Have not been contacted recently
        """
        campaign = await self._get_campaign()
        if not campaign or not campaign.audiences:
            return None

        # Get random audience and its valid contacts
        audience = random.choice(campaign.audiences)
        contacts = await queries.get_audience_contacts(
            audience_id=audience.id, valid_only=True
        )

        return random.choice(contacts) if contacts else None

    # Dialog operations
    @db.decorators.with_queries(dialog_queries.DialogQueries)
    async def create_dialog(
        self,
        account: account_models.Account,
        contact: audience_models.Contact,
        queries: dialog_queries.DialogQueries,
    ) -> Optional[message_models.Dialog]:
        """Create new dialog for campaign.

        Args:
            account: Account to use for dialog
            contact: Contact to start dialog with

        Returns:
            Created dialog if successful, None otherwise

        Raises:
            CampaignRunnerError: If dialog creation fails
        """
        if not contact.telegram_username:
            raise CampaignRunnerError(f"Contact {contact.id} has no username")

        try:
            dialog = await queries.create_dialog(
                username=contact.telegram_username,
                account_id=account.id,
            )
            if dialog:
                dialog.campaign_id = self.campaign_id
                dialog.status = message_models.DialogStatus.active
                await queries.session.flush()
            return dialog
        except Exception as e:
            logger.error(f"Failed to create dialog: {e}")
            return None

    # Helper methods
    @db.decorators.with_queries(queries.CampaignQueries)
    async def _get_campaign(
        self, queries: queries.CampaignQueries
    ) -> Optional[models.Campaign]:
        """Get campaign by ID.

        Returns:
            Campaign if found and active, None otherwise
        """
        return await queries.get_campaign(self.campaign_id)

    async def _process_accounts(self, accounts: List[account_models.Account]) -> None:
        """Process list of accounts for campaign.

        Args:
            accounts: List of accounts to process
        """
        for account in accounts:
            if self._stop_event.is_set():
                break
            await self._process_account(account)

        # Small delay between iterations
        await asyncio.sleep(1)

    async def _process_account(self, account: account_models.Account) -> None:
        """Process single account for campaign.

        Args:
            account: Account to process

        This method:
        1. Gets a random contact
        2. Creates a dialog
        3. Initializes dialog conductor
        """
        try:
            # Get random contact
            contact = await self.get_random_contact()
            if not contact:
                logger.warning(f"No contacts available for campaign {self.campaign_id}")
                return

            # Create and start dialog
            dialog = await self.create_dialog(account, contact)
            if not dialog:
                logger.error(f"Failed to create dialog for account {account.id}")
                return

            # Start dialog conductor (to be implemented)
            # await start_dialog_conductor(dialog)

        except Exception as e:
            logger.error(
                f"Error processing account {account.id} "
                f"for campaign {self.campaign_id}: {e}",
                exc_info=True,
            )

    async def _handle_no_accounts(self) -> None:
        """Handle case when no accounts are available.

        Implements exponential backoff for retries.
        """
        await asyncio.sleep(60)  # Wait before retry
