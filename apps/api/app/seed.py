from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Company, Site, SiteUser, User, UserRole
from app.security import hash_password


def seed() -> None:
    db: Session = SessionLocal()
    try:
        company = db.query(Company).first()
        if not company:
            company = Company(name=settings.initial_company_name, timezone="Asia/Kolkata")
            db.add(company)
            db.flush()

        site = (
            db.query(Site)
            .filter(Site.company_id == company.id, Site.code == settings.initial_site_code.upper())
            .first()
        )
        if not site:
            site = Site(
                company_id=company.id,
                name=settings.initial_site_name,
                code=settings.initial_site_code.upper(),
                status="active",
            )
            db.add(site)
            db.flush()
        elif site.name != settings.initial_site_name:
            site.name = settings.initial_site_name

        email = settings.initial_owner_email.lower().strip()
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = (
                db.query(User)
                .filter(User.company_id == company.id, User.global_role == UserRole.OWNER.value)
                .order_by(User.created_at)
                .first()
            )
        if not user:
            user = User(
                company_id=company.id,
                email=email,
                password_hash=hash_password(settings.initial_owner_password),
                name=settings.initial_owner_name,
                is_active=True,
                global_role=UserRole.OWNER.value,
            )
            db.add(user)
            db.flush()
        else:
            user.email = email
            user.name = settings.initial_owner_name
            user.password_hash = hash_password(settings.initial_owner_password)
            user.is_active = True
            user.global_role = UserRole.OWNER.value

        weak = settings.initial_owner_password.strip().lower() in {"changeme", "change-me", "change_me"}
        user.must_change_password = weak

        link = (
            db.query(SiteUser)
            .filter(SiteUser.site_id == site.id, SiteUser.user_id == user.id)
            .first()
        )
        if not link:
            db.add(SiteUser(site_id=site.id, user_id=user.id, role=UserRole.OWNER.value))

        db.commit()
        print(f"Seeded company={company.name} site={site.code} owner={user.email}")
        if weak:
            print("WARNING: Change INITIAL_OWNER_PASSWORD and JWT_SECRET before production.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
