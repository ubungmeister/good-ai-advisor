from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.customer_profile import CustomerProfile
from app.models.policy import Policy
from app.models.product import Product
from app.models.product_version import ProductVersion
from app.models.user import User


TEST_EMAIL = "test@example.com"
PRODUCT_CODE = "TRAVEL_INSURANCE"
PRODUCT_VERSION = "2026.1"
POLICY_NUMBER = "TI-2026-0001"


def seed():
    db = SessionLocal()

    try:
        # -------------------------
        # 1. USER
        # -------------------------

        user = db.scalar(
            select(User).where(
                User.email == TEST_EMAIL
            )
        )

        if user is None:
            user = User(
                email=TEST_EMAIL,
                status="ACTIVE",
            )

            user.profile = CustomerProfile(
                first_name="Max",
                last_name="Test",
                date_of_birth=date(1995, 1, 1),
                birth_number="TEST-950101",
                phone="+420000000000",
            )

            db.add(user)

            # Send INSERT to DB so user.id exists,
            # but do not commit yet.
            db.flush()

            print("Created test user.")

        # -------------------------
        # 2. PRODUCT
        # -------------------------

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

        # -------------------------
        # 3. PRODUCT VERSION
        # -------------------------

        product_version = db.scalar(
            select(ProductVersion).where(
                ProductVersion.product_id == product.id,
                ProductVersion.version == PRODUCT_VERSION,
            )
        )

        if product_version is None:
            product_version = ProductVersion(
                product_id=product.id,
                version=PRODUCT_VERSION,
                valid_from=date(2026, 1, 1),
                valid_to=date(2026, 12, 31),
            )

            db.add(product_version)
            db.flush()

            print("Created product version.")

        # -------------------------
        # 4. POLICY
        # -------------------------

        policy = db.scalar(
            select(Policy).where(
                Policy.policy_number == POLICY_NUMBER
            )
        )

        if policy is None:
            policy = Policy(
                user_id=user.id,
                product_version_id=product_version.id,

                policy_number=POLICY_NUMBER,
                status="ACTIVE",

                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 15),

                territory_code="EUROPE",

                premium_amount=Decimal("1290.00"),
                currency="CZK",
            )

            db.add(policy)

            print("Created policy.")

        # -------------------------
        # SAVE EVERYTHING
        # -------------------------

        db.commit()

        print("Seed completed successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed()