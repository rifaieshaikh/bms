from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.access import AppUser, ProjectMembership
from vaybooks.bms.domain.shared.enums import ProjectAppRole


class MongoAppUserRepository:
    def __init__(self, db: Database):
        self._collection = db.app_users

    def _to_doc(self, user: AppUser) -> dict:
        return {
            "_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "global_roles": [r.value for r in user.global_roles],
            "active": user.active,
            "password_hash": user.password_hash,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    def _from_doc(self, doc: dict) -> AppUser:
        roles = []
        for raw in doc.get("global_roles") or []:
            try:
                roles.append(ProjectAppRole(raw))
            except ValueError:
                continue
        return AppUser(
            id=doc["_id"],
            username=doc.get("username", ""),
            display_name=doc.get("display_name", ""),
            global_roles=roles,
            active=bool(doc.get("active", True)),
            password_hash=doc.get("password_hash", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, user: AppUser) -> AppUser:
        self._collection.replace_one({"_id": user.id}, self._to_doc(user), upsert=True)
        return user

    def find_by_id(self, user_id: str) -> Optional[AppUser]:
        doc = self._collection.find_one({"_id": user_id})
        return self._from_doc(doc) if doc else None

    def find_by_username(self, username: str) -> Optional[AppUser]:
        doc = self._collection.find_one({"username": (username or "").strip()})
        return self._from_doc(doc) if doc else None

    def list_all(self) -> List[AppUser]:
        return [self._from_doc(d) for d in self._collection.find().sort("username", 1)]


class MongoProjectMembershipRepository:
    def __init__(self, db: Database):
        self._collection = db.project_memberships

    def _to_doc(self, m: ProjectMembership) -> dict:
        return {
            "_id": m.id,
            "project_id": m.project_id,
            "user_id": m.user_id,
            "role": m.role.value,
            "created_at": m.created_at,
        }

    def _from_doc(self, doc: dict) -> ProjectMembership:
        return ProjectMembership(
            id=doc["_id"],
            project_id=doc["project_id"],
            user_id=doc["user_id"],
            role=ProjectAppRole(doc.get("role", ProjectAppRole.PROJECT_MANAGER.value)),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, membership: ProjectMembership) -> ProjectMembership:
        self._collection.replace_one(
            {"_id": membership.id}, self._to_doc(membership), upsert=True
        )
        return membership

    def list_by_project(self, project_id: str) -> List[ProjectMembership]:
        docs = self._collection.find({"project_id": project_id})
        return [self._from_doc(d) for d in docs]

    def list_by_user(self, user_id: str) -> List[ProjectMembership]:
        docs = self._collection.find({"user_id": user_id})
        return [self._from_doc(d) for d in docs]
