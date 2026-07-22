"""Seed system project activity catalog entries."""

from __future__ import annotations

from pymongo.database import Database


def up(db: Database) -> None:
    from vaybooks.bms.domain.projects.activity_catalog import ProjectActivityConfig
    from vaybooks.bms.domain.shared.enums import ActivityCategory
    from vaybooks.bms.infrastructure.repositories.projects.mongo_project_activity_config_repository import (
        MongoProjectActivityConfigRepository,
    )

    repo = MongoProjectActivityConfigRepository(db)
    if repo.list_all(active_only=False):
        return

    seeds = [
        ("Demolition", ActivityCategory.IN_HOUSE_SERVICE, 250.0, 0.0),
        ("Electrical", ActivityCategory.IN_HOUSE_SERVICE, 300.0, 0.0),
        ("Civil Works", ActivityCategory.IN_HOUSE_SERVICE, 280.0, 0.0),
        ("Plumbing", ActivityCategory.IN_HOUSE_SERVICE, 280.0, 0.0),
        ("Carpentry", ActivityCategory.IN_HOUSE_SERVICE, 350.0, 0.0),
        ("Painting", ActivityCategory.IN_HOUSE_SERVICE, 200.0, 0.0),
        ("Material Supply", ActivityCategory.IN_HOUSE_MATERIAL, 0.0, 0.0),
        ("Specialist Subcon", ActivityCategory.OUTSOURCED_SERVICE, 0.0, 0.0),
    ]

    for name, category, hourly, amount in seeds:
        config = ProjectActivityConfig(
            activity_name=name,
            activity_type=None,
            default_hourly_rate=hourly,
            default_amount=amount,
            is_system=True,
        )
        config.apply_category(category)
        repo.save(config)
