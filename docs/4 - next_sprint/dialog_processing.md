# Dialog Processing Architecture

## Components

### CampaignRunner
Responsible for running multiple campaigns concurrently. For each campaign:
1. Gets available accounts linked to the campaign
2. For each available account:
   - Checks account safety limits (messages/hour, messages/day)
   - Gets random contact from campaign audiences that hasn't been contacted
   - Initiates new dialog

```python
async def run_campaign(campaign_id: int):
    campaign = await get_campaign(campaign_id)
    while campaign.status == CampaignStatus.active:
        accounts = await get_campaign_accounts(campaign_id)
        for account in accounts:
            if not await check_account_safety(account):
                continue

            contact = await get_random_available_contact(campaign_id)
            if not contact:
                continue

            dialog = await create_dialog(account, contact, campaign)
            await start_dialog_conductor(dialog)
```

### DialogConductor
Manages individual dialog flow using specified engine type and prompt template.
1. Initializes appropriate dialog engine
2. Sends initial message
3. Processes incoming updates
4. Handles message sending through account safety middleware

```python
class DialogConductor:
    def __init__(self, dialog: Dialog):
        self.dialog = dialog
        self.engine = create_engine(
            dialog.campaign.engine_type,
            dialog.campaign.prompt_template
        )

    async def process_update(self, update: Message):
        # Get response from engine
        response = await self.engine.get_response(update)
        if response:
            # Send through safety middleware
            await self.send_message(response)

    async def send_message(self, text: str):
        # Check account safety before sending
        if not await check_account_safety(self.dialog.account):
            await self.pause_dialog()
            return
        await send_telegram_message(self.dialog, text)
```

### DialogReviver
Separate process that monitors "stuck" dialogs and attempts to revive them:
1. Finds dialogs without recent messages
2. Asks engine for follow-up message
3. Marks dialog as dead if engine determines it's irrecoverable

```python
async def revive_dialogs():
    while True:
        stuck_dialogs = await find_stuck_dialogs()
        for dialog in stuck_dialogs:
            conductor = DialogConductor(dialog)

            # Ask engine if dialog can be revived
            follow_up = await conductor.engine.get_follow_up()
            if follow_up:
                await conductor.send_message(follow_up)
            elif await conductor.engine.is_dialog_dead():
                await mark_dialog_finished(dialog)
```

### AccountSafetyMiddleware
Centralized place for account safety checks:
1. Message rate limiting
2. Daily/hourly message limits
3. Account status monitoring
4. Automatic dialog status updates on account block

```python
class AccountSafetyMiddleware:
    @staticmethod
    async def check_account(account: Account) -> bool:
        return (
            account.status == AccountStatus.active
            and not account.is_in_flood_wait
            and AccountSafety.can_send_message(account)
        )

    @staticmethod
    async def on_account_blocked(account: Account):
        # Mark all active dialogs as blocked
        await update_account_dialogs(
            account_id=account.id,
            old_status=DialogStatus.active,
            new_status=DialogStatus.blocked
        )
```

## Startup Process

1. Load all active campaigns
2. For each campaign:
   - Start CampaignRunner
   - Resume active dialogs through DialogConductor

3. Start DialogReviver process

```python
async def startup():
    # Resume existing dialogs
    active_dialogs = await get_active_dialogs()
    for dialog in active_dialogs:
        if await check_account_safety(dialog.account):
            await start_dialog_conductor(dialog)

    # Start campaigns
    campaigns = await get_active_campaigns()
    for campaign in campaigns:
        asyncio.create_task(run_campaign(campaign.id))

    # Start reviver
    asyncio.create_task(revive_dialogs())
```

## Error Handling

1. Account gets blocked:
   - Mark account as blocked/disabled
   - Mark all active dialogs as blocked
   - Remove account from active campaigns

2. Message sending fails:
   - If flood wait - pause account for specified duration
   - If other error - retry with exponential backoff
   - If critical error - mark dialog as error and notify

3. Engine errors:
   - Log error details
   - Mark dialog as error
   - Notify monitoring system
