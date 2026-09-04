from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.database import SessionLocal

from app.models.person import Person
from app.models.plan import Plan

from app.models.policy import (
    PaymentStatus,
    Policy,
    PolicyStatus,
)

from app.models.travel_policy_detail import (
    CoverageMode,
    SportLevel,
    TerritoryType,
    TravelPolicyDetail,
    TripPurpose,
)

from app.models.policy_person import (
    PersonRole,
    PolicyPerson,
)

from app.models.product import Product
from app.models.product_version import ProductVersion
from app.models.user import User


TEST_EMAIL = "test@example.com"

PRODUCT_CODE = "TRAVEL_INSURANCE"
PRODUCT_VERSION = "2026.1"

POLICY_NUMBER = "TI-2026-0001"


def seed() -> None:
    db = SessionLocal()

    try:
        # =====================================================
        # 1. USER + PERSON
        # =====================================================

        user = db.scalar(
            select(User)
            .options(joinedload(User.person))
            .where(User.email == TEST_EMAIL)
        )

        if user is None:
            person = Person(
                first_name="Max",
                last_name="Test",
                date_of_birth=date(1995, 1, 1),
                birth_number="TEST-950101",
                phone="+420000000000",
            )

            user = User(
                email=TEST_EMAIL,
                status="ACTIVE",
                person=person,
            )

            db.add(user)
            db.flush()

            print("Created test user and person.")

        else:
            print("Test user already exists.")

        # =====================================================
        # 2. PRODUCT
        # =====================================================

        product = db.scalar(
            select(Product).where(
                Product.code == PRODUCT_CODE
            )
        )

        if product is None:
            product = Product(
                code=PRODUCT_CODE,
                name="Travel Insurance",
                product_type="TRAVEL",
                is_active=True,
            )

            db.add(product)
            db.flush()

            print("Created product.")

        else:
            print("Product already exists.")

        # =====================================================
        # 3. PRODUCT VERSION
        # =====================================================

        product_version = db.scalar(
            select(ProductVersion).where(
                ProductVersion.product_id == product.id,
                ProductVersion.version == PRODUCT_VERSION,
            )
        )

        if product_version is None:
            product_version = ProductVersion(
                product=product,
                version=PRODUCT_VERSION,
                valid_from=date(2026, 1, 1),
                valid_to=date(2026, 12, 31),
                is_active=True,
            )

            db.add(product_version)
            db.flush()

            print("Created product version.")

        else:
            print("Product version already exists.")

        # =====================================================
        # 4. PLANS
        # =====================================================

        plans_data = [
            (
                "STANDARD",
                "Standard",
                "Basic travel insurance package",
            ),
            (
                "DOMINANT",
                "Dominant",
                "Extended travel insurance package",
            ),
            (
                "PREMIANT",
                "Premiant",
                "Premium travel insurance package",
            ),
        ]

        for code, name, description in plans_data:
            plan = db.scalar(
                select(Plan).where(
                    Plan.product_version_id == product_version.id,
                    Plan.code == code,
                )
            )

            if plan is None:
                plan = Plan(
                    product_version=product_version,
                    code=code,
                    name=name,
                    description=description,
                    is_active=True,
                )

                db.add(plan)

                print(f"Created plan: {code}")

            else:
                print(f"Plan already exists: {code}")

        # SessionLocal has autoflush=False.
        # We need newly created plans to exist in PostgreSQL
        # before selecting one below.
        db.flush()

        # =====================================================
        # 5. SELECT PLAN FOR TEST POLICY
        # =====================================================

        selected_plan = db.scalar(
            select(Plan).where(
                Plan.product_version_id == product_version.id,
                Plan.code == "PREMIANT",
            )
        )

        if selected_plan is None:
            raise RuntimeError(
                "PREMIANT plan was not found."
            )

        # =====================================================
        # 6. POLICY
        # =====================================================

        policy = db.scalar(
            select(Policy).where(
                Policy.policy_number == POLICY_NUMBER
            )
        )

        if policy is None:
            policy = Policy(
                owner=user,
                product_version=product_version,
                plan=selected_plan,

                policy_number=POLICY_NUMBER,

                policy_status=PolicyStatus.ACTIVE,
                payment_status=PaymentStatus.PAID,

                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 15),

                premium_amount=Decimal("1290.00"),
                currency="CZK",

                paid_at=datetime(2026, 8, 25, 10, 0),
            )

            db.add(policy)

            print("Created policy.")

        else:
            print("Policy already exists.")

        # We need policy.id for TravelPolicyDetail
        # and PolicyPerson.
        db.flush()

        # =====================================================
        # 7. TRAVEL POLICY DETAILS
        # =====================================================

        travel_details = db.scalar(
            select(TravelPolicyDetail).where(
                TravelPolicyDetail.policy_id == policy.id
            )
        )

        if travel_details is None:
            travel_details = TravelPolicyDetail(
                policy=policy,

                coverage_mode=CoverageMode.SINGLE_TRIP,
                territory=TerritoryType.EUROPE,

                destination_country_code="DE",

                trip_purpose=TripPurpose.LEISURE,
                sport_level=SportLevel.RECREATIONAL,

                departure_date=date(2026, 9, 1),
                return_date=date(2026, 9, 15),
            )

            db.add(travel_details)

            print("Created travel policy details.")

        else:
            print("Travel policy details already exist.")

        # =====================================================
        # 8. POLICY PERSON
        # =====================================================

        if user.person is None:
            raise RuntimeError(
                "Test user has no Person."
            )

        policy_person = db.scalar(
            select(PolicyPerson).where(
                PolicyPerson.policy_id == policy.id,
                PolicyPerson.person_id == user.person.id,
                PolicyPerson.role == PersonRole.POLICYHOLDER,
            )
        )

        if policy_person is None:
            policy_person = PolicyPerson(
                policy_id=policy.id,
                person_id=user.person.id,

                role=PersonRole.POLICYHOLDER,

                coverage_start=policy.start_date,
                coverage_end=policy.end_date,
            )

            db.add(policy_person)

            print("Created policy person: POLICYHOLDER.")

        else:
            print("Policy person already exists.")

        # =====================================================
        # 9. SAVE
        # =====================================================

        db.commit()

        print("Seed completed successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed()