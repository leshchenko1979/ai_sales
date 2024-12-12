"""Company-specific UI operations."""

import asyncio
import json
from pathlib import Path

import questionary
import yaml
from core import db
from core.companies import queries as company_queries
from core.companies.models import Company

from ..styles import STYLE


class CompanyUI:
    """Company UI operations for managing company data and descriptions."""

    def __init__(self, manager):
        """
        Initialize CompanyUI.

        Args:
            manager: Parent UI manager instance
        """
        self.manager = manager
        self.workspace_root = Path(__file__).parent.parent.parent.parent.parent
        self.companies_dir = self.workspace_root / "data" / "companies"

    # Core operations
    @db.with_queries(company_queries.CompanyQueries)
    async def view_companies(self, queries: company_queries.CompanyQueries):
        """View and manage existing companies."""
        while True:
            try:
                companies = await queries.get_all_companies()
                if not companies:
                    print("No companies found")
                    await self.manager._pause()
                    return

                selected_id = await self._select_company(companies)
                if selected_id == "back":
                    # Just return without pause when going back
                    return

                company = next((c for c in companies if c.id == selected_id), None)
                if company:
                    await self._edit_company_details(queries, company)

            except (KeyboardInterrupt, asyncio.CancelledError):
                break
            except Exception as e:
                self.manager._handle_error(e)
                await self.manager._pause()

    @db.with_queries(company_queries.CompanyQueries)
    async def create_company(self, queries: company_queries.CompanyQueries):
        """Create a new company with descriptions."""
        try:
            print("\nCreate New Company")
            self.manager.print_separator()

            name = await self._get_company_name()
            if not name:
                return

            is_active = await questionary.confirm(
                "Set company as active?", default=True
            ).ask_async()

            company = await self._create_company_base(queries, name, is_active)
            if not company:
                return

            # Use consolidated description loading without confirmation
            await self._load_and_update_descriptions(queries, company)

        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nCompany creation cancelled")
        except Exception as e:
            self.manager._handle_error(e)
        finally:
            await self.manager._pause()

    # Secondary operations
    async def _edit_company_details(
        self, queries: company_queries.CompanyQueries, company: Company
    ):
        """
        Edit company details menu.

        Args:
            queries: Company queries instance
            company: Company to edit
        """
        while True:
            try:
                print(f"\nEditing Company: {company.name}")
                self.manager.print_separator()

                action = await self._get_edit_action()
                if action == 0:
                    break

                if action == 1:
                    company = await self._edit_basic_info(queries, company)
                    await self.manager._pause()
                elif action == 2:
                    # Don't pause after description edit if cancelled
                    success = await self._edit_company_descriptions(queries, company)
                    if success:  # Only pause if operation was completed
                        await self.manager._pause()
                elif action == 3:
                    company = await self._edit_company_status(queries, company)
                    await self.manager._pause()

            except (KeyboardInterrupt, asyncio.CancelledError):
                break
            except Exception as e:
                self.manager._handle_error(e)
                await self.manager._pause()

    # Helper methods
    async def _display_companies_list(self, companies: list[Company]):
        """Display list of companies with details."""
        print("\nAvailable Companies:")
        self.manager.print_separator()
        for company in companies:
            self._display_company_info(company)
            self.manager.print_separator()

    async def _select_company(self, companies: list[Company]) -> str:
        """Show company selection menu."""
        choices = [
            questionary.Choice(
                f"{company.name} (ID: {company.id}, {'active' if company.is_active else 'inactive'})",
                company.id,
            )
            for company in companies
        ]
        choices.append(questionary.Choice("Back", "back"))

        return await questionary.select(
            "Select company to edit:", choices=choices, style=STYLE
        ).ask_async()

    async def _get_company_name(self) -> str:
        """Get and validate company name."""
        name = await questionary.text("Enter company name:").ask_async()
        if not name or not name.strip():
            print("Company name cannot be empty")
            return ""
        return name.strip()

    async def _create_company_base(
        self, queries: company_queries.CompanyQueries, name: str, is_active: bool
    ) -> Company | None:
        """Create base company record."""
        company = await queries.create_company(name=name, is_active=is_active)
        if not company:
            print("Failed to create company")
            return None
        print(f"\nCreated company: {company.name}")
        return company

    # Helper methods (continued...)
    def _display_company_info(self, company: Company):
        """
        Display formatted company information.

        Args:
            company: Company instance to display
        """
        status = "active" if company.is_active else "inactive"
        print(f"ID: {company.id}")
        print(f"Name: {company.name}")
        print(f"Status: {status}")

        if not company.descriptions:
            print("No descriptions available")
            return

        for field, value in company.descriptions.items():
            print(f"\n{field.title()}:")
            self.manager.print_separator()
            self._display_description_value(value)

    def _display_description_value(self, value: dict | str):
        """
        Display description value with proper formatting.

        Args:
            value: Description value to display (dict or str)
        """
        if isinstance(value, dict):
            for subfield, subvalue in value.items():
                print(f"\n{subfield.title()}:")
                print(self._truncate_text(subvalue.strip()))
        else:
            paragraphs = value.strip().split("\n\n")
            for i, paragraph in enumerate(paragraphs):
                lines = paragraph.split("\n")
                for line in lines:
                    if line.strip().startswith("-"):
                        print(f"  {line.strip()}")
                    elif line.strip().startswith("*"):
                        print(f"    {line.strip()}")
                    else:
                        print(self._truncate_text(line.strip()))
                if i < len(paragraphs) - 1:
                    print("")

    def _truncate_text(self, text: str, max_length: int = 100) -> str:
        """
        Truncate text if it exceeds maximum length.

        Args:
            text: Text to truncate
            max_length: Maximum allowed length

        Returns:
            Truncated text if needed, original text otherwise
        """
        return text if len(text) <= max_length else f"{text[:max_length - 3]}..."

    async def _get_edit_action(self) -> int:
        """
        Show edit action selection menu.

        Returns:
            Selected action ID
        """
        return await questionary.select(
            "Select action:",
            choices=[
                questionary.Choice("Edit Basic Info", 1),
                questionary.Choice("Edit Descriptions", 2),
                questionary.Choice("Change Status", 3),
                questionary.Choice("Back", 0),
            ],
            style=STYLE,
        ).ask_async()

    async def _edit_basic_info(
        self, queries: company_queries.CompanyQueries, company: Company
    ) -> Company:
        """
        Edit company's basic information.

        Args:
            queries: Company queries instance
            company: Company to edit

        Returns:
            Updated company instance
        """
        name = await questionary.text(
            "New company name:", default=company.name
        ).ask_async()

        if name != company.name:
            updated_company = await queries.update_company(
                company_id=company.id,
                name=name,
                descriptions=company.descriptions,
            )
            if updated_company:
                print(f"Updated name to: {updated_company.name}")
                return updated_company
            print("Failed to update name")

        return company

    async def _edit_company_status(
        self, queries: company_queries.CompanyQueries, company: Company
    ) -> Company:
        """
        Edit company's active status.

        Args:
            queries: Company queries instance
            company: Company to edit

        Returns:
            Updated company instance
        """
        is_active = await questionary.confirm(
            "Set company as active?", default=company.is_active
        ).ask_async()

        if is_active != company.is_active:
            updated_company = await queries.update_company_status(company.id, is_active)
            if updated_company:
                status = "active" if updated_company.is_active else "inactive"
                print(f"Updated status to {status}")
                return updated_company
            print("Failed to update status")

        return company

    async def _update_company_descriptions(
        self,
        queries: company_queries.CompanyQueries,
        company: Company,
        descriptions: dict,
    ) -> bool:
        """
        Update company descriptions.

        Args:
            queries: Company queries instance
            company: Company to update
            descriptions: New descriptions to set

        Returns:
            True if update successful, False otherwise
        """
        updated_company = await queries.update_company(
            company_id=company.id,
            name=company.name,
            descriptions=descriptions,
        )
        return bool(updated_company)

    async def _edit_company_descriptions(
        self, queries: company_queries.CompanyQueries, company: Company
    ) -> bool:
        """
        Edit company descriptions by loading from file.

        Args:
            queries: Company queries instance
            company: Company to edit

        Returns:
            True if descriptions were updated, False if cancelled or failed
        """
        return await self._load_and_update_descriptions(queries, company)

    async def _load_and_update_descriptions(
        self,
        queries: company_queries.CompanyQueries,
        company: Company,
        error_pause: bool = True,
    ) -> bool:
        """
        Load descriptions from file and update company.

        Args:
            queries: Company queries instance
            company: Company to update
            error_pause: Whether to pause on errors

        Returns:
            True if update successful, False otherwise
        """
        description_files = await self._get_description_files()
        if not description_files:
            print(f"No description files found in {self.companies_dir}")
            return False

        selected_file = await self._select_description_file(description_files)
        if not selected_file:
            # Just return silently on cancel
            return False

        try:
            file_descriptions = await self._load_descriptions_from_file(selected_file)
            if not file_descriptions:
                print("Failed to load descriptions from file")
                return False

            success = await self._update_company_descriptions(
                queries, company, file_descriptions
            )
            print(
                "\nUpdated company descriptions"
                if success
                else "Failed to update descriptions"
            )
            return success

        except (KeyboardInterrupt, asyncio.CancelledError):
            raise
        except Exception as e:
            self.manager._handle_error(e)
            return False

    async def _get_description_files(self) -> list[Path]:
        """
        Get list of available description files.

        Returns:
            List of paths to description files
        """
        if not self.companies_dir.exists():
            print(f"Creating directory: {self.companies_dir}")
            self.companies_dir.mkdir(parents=True, exist_ok=True)

        # Use glob patterns for both JSON and YAML files
        json_files = list(self.companies_dir.glob("*.json"))
        yaml_files = list(
            self.companies_dir.glob("*.y*ml")
        )  # matches both .yml and .yaml

        all_files = json_files + yaml_files
        if not all_files:
            print(f"No description files found in {self.companies_dir}")
            print("Please add .json, .yml, or .yaml files with company descriptions")

        return all_files

    async def _select_description_file(
        self, description_files: list[Path]
    ) -> Path | None:
        """
        Show file selection menu and return selected file.

        Args:
            description_files: List of available description files

        Returns:
            Selected file path or None if cancelled
        """
        choices = [
            questionary.Choice(str(file.relative_to(self.companies_dir)), file)
            for file in description_files
        ]
        choices.append(questionary.Choice("Cancel", None))

        selected = await questionary.select(
            "Select description file:", choices=choices, style=STYLE
        ).ask_async()

        return None if selected is None or str(selected) == "Cancel" else selected

    async def _load_descriptions_from_file(self, file_path: Path) -> dict | None:
        """
        Load descriptions from JSON/YAML file.

        Args:
            file_path: Path to description file

        Returns:
            Dict with descriptions or None on error
        """
        with open(file_path, "r", encoding="utf-8") as f:
            if file_path.suffix.lower() == ".json":
                return json.load(f)
            elif file_path.suffix.lower() in {".yml", ".yaml"}:
                return yaml.safe_load(f)
        return None
