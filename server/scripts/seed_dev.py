from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.database import SessionLocal

from app.models.person import Person
from app.models.plan import Plan
from app.models.coverage_type import CoverageType
from app.models.plan_coverage import PlanCoverage
from app.models.policy_coverage import PolicyCoverage
from app.models.policy_option import PolicyOption

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
        # COVERAGE TYPES
        # =====================================================

        coverage_types_data = [
            (
                "MEDICAL_EXPENSES",
                "Medical Expenses",
                "MEDICAL",
                "Medical treatment expenses during travel.",
            ),
            (
                "DENTAL",
                "Dental Treatment",
                "MEDICAL",
                "Emergency dental treatment.",
            ),
            (
                "ASSISTANCE",
                "Assistance Services",
                "ASSISTANCE",
                "Assistance services during travel.",
            ),
            (
                "ACCIDENT",
                "Accident",
                "ACCIDENT",
                "Coverage related to accidental injury.",
            ),
            (
                "LIABILITY",
                "Liability",
                "LIABILITY",
                "Liability for damage caused to another person.",
            ),
            (
                "LEGAL_PROTECTION",
                "Legal Protection",
                "LEGAL",
                "Legal assistance and protection.",
            ),
            (
                "BAGGAGE",
                "Baggage",
                "PROPERTY",
                "Coverage for baggage loss or damage.",
            ),
            (
                "TRIP_INTERRUPTION",
                "Trip Interruption",
                "TRAVEL_DISRUPTION",
                "Coverage when a trip must be interrupted.",
            ),
            (
                "MISSED_DEPARTURE",
                "Missed Departure",
                "TRAVEL_DISRUPTION",
                "Coverage for certain missed departures.",
            ),
            (
                "BAGGAGE_DELAY",
                "Baggage Delay",
                "TRAVEL_DISRUPTION",
                "Coverage for delayed baggage.",
            ),
            (
                "FLIGHT_DELAY",
                "Flight Delay",
                "TRAVEL_DISRUPTION",
                "Coverage for flight delays.",
            ),
            (
                "CANCELLATION",
                "Cancellation",
                "TRAVEL_DISRUPTION",
                "Coverage for eligible trip cancellation.",
            ),
        ]

        for code, name, category, description in coverage_types_data:
            coverage_type = db.scalar(
                select(CoverageType).where(
                    CoverageType.code == code
                )
            )

            if coverage_type is None:
                coverage_type = CoverageType(
                    code=code,
                    name=name,
                    category=category,
                    description=description,
                )

                db.add(coverage_type)

                print(f"Created coverage type: {code}")

            else:
                print(f"Coverage type already exists: {code}")

        db.flush()
        # =====================================================
        # PLAN COVERAGES
        # =====================================================

        plan_coverages_data = [
            # PLAN, COVERAGE, INCLUDED, LIMIT, CURRENCY
            (
                "STANDARD",
                "MEDICAL_EXPENSES",
                True,
                Decimal("5000000.00"),
                "CZK",
            ),
            (
                "STANDARD",
                "ASSISTANCE",
                True,
                None,
                None,
            ),

            (
                "DOMINANT",
                "MEDICAL_EXPENSES",
                True,
                Decimal("10000000.00"),
                "CZK",
            ),
            (
                "DOMINANT",
                "ASSISTANCE",
                True,
                None,
                None,
            ),
            (
                "DOMINANT",
                "BAGGAGE",
                True,
                Decimal("50000.00"),
                "CZK",
            ),
            (
                "DOMINANT",
                "LIABILITY",
                True,
                Decimal("5000000.00"),
                "CZK",
            ),

            (
                "PREMIANT",
                "MEDICAL_EXPENSES",
                True,
                Decimal("100000000.00"),
                "CZK",
            ),
            (
                "PREMIANT",
                "ASSISTANCE",
                True,
                None,
                None,
            ),
            (
                "PREMIANT",
                "BAGGAGE",
                True,
                Decimal("100000.00"),
                "CZK",
            ),
            (
                "PREMIANT",
                "LIABILITY",
                True,
                Decimal("20000000.00"),
                "CZK",
            ),
        ]

        for (
                plan_code,
                coverage_code,
                included,
                limit_amount,
                currency,
        ) in plan_coverages_data:

            plan = db.scalar(
                select(Plan).where(
                    Plan.product_version_id == product_version.id,
                    Plan.code == plan_code,
                )
            )

            coverage_type = db.scalar(
                select(CoverageType).where(
                    CoverageType.code == coverage_code
                )
            )

            if plan is None:
                raise RuntimeError(
                    f"Plan not found: {plan_code}"
                )

            if coverage_type is None:
                raise RuntimeError(
                    f"Coverage type not found: {coverage_code}"
                )

            plan_coverage = db.scalar(
                select(PlanCoverage).where(
                    PlanCoverage.plan_id == plan.id,
                    PlanCoverage.coverage_type_id == coverage_type.id,
                )
            )

            if plan_coverage is None:
                plan_coverage = PlanCoverage(
                    plan_id=plan.id,
                    coverage_type_id=coverage_type.id,

                    included=included,

                    limit_amount=limit_amount,
                    currency=currency,

                    coverage_level=None,
                    deductible_type=None,
                    deductible_value=None,
                    parameters=None,
                )

                db.add(plan_coverage)

                print(
                    f"Created plan coverage: "
                    f"{plan_code} -> {coverage_code}"
                )

            else:
                print(
                    f"Plan coverage already exists: "
                    f"{plan_code} -> {coverage_code}"
                )
            db.flush()
        # =====================================================
        # POLICY COVERAGES
        # =====================================================

        plan_coverages = db.scalars(
            select(PlanCoverage).where(
                PlanCoverage.plan_id == policy.plan_id,
                PlanCoverage.included.is_(True),
            )
        ).all()

        for plan_coverage in plan_coverages:

            policy_coverage = db.scalar(
                select(PolicyCoverage).where(
                    PolicyCoverage.policy_id == policy.id,
                    PolicyCoverage.coverage_type_id
                    == plan_coverage.coverage_type_id,
                    PolicyCoverage.policy_person_id.is_(None),
                )
            )

            if policy_coverage is None:

                policy_coverage = PolicyCoverage(
                    policy_id=policy.id,

                    coverage_type_id=plan_coverage.coverage_type_id,

                    policy_person_id=None,

                    source_plan_coverage_id=plan_coverage.id,

                    status="ACTIVE",

                    limit_amount=plan_coverage.limit_amount,
                    currency=plan_coverage.currency,

                    coverage_level=plan_coverage.coverage_level,

                    deductible_type=plan_coverage.deductible_type,
                    deductible_value=plan_coverage.deductible_value,

                    parameters=plan_coverage.parameters,
                )

                db.add(policy_coverage)

                print(
                    f"Created policy coverage: "
                    f"{plan_coverage.coverage_type.code}"
                )

            else:
                print(
                    f"Policy coverage already exists: "
                    f"{plan_coverage.coverage_type.code}"
                )

        # =====================================================
        # POLICY OPTIONS
        # =====================================================

        policy_options_data = [
            (
                "WINTER_SPORTS",
                "Winter Sports",
                True,
                None,
                Decimal("500.00"),
                "CZK",
                {
                    "skiing": True,
                    "snowboarding": True,
                },
            ),
            (
                "CANCELLATION",
                "Trip Cancellation",
                True,
                "STANDARD",
                Decimal("300.00"),
                "CZK",
                {
                    "max_trip_price": 50000,
                },
            ),
            (
                "VEHICLE_ASSISTANCE",
                "Vehicle Assistance",
                False,
                None,
                None,
                None,
                None,
            ),
        ]

        for (
                code,
                name,
                selected,
                variant,
                premium_amount,
                currency,
                parameters,
        ) in policy_options_data:

            policy_option = db.scalar(
                select(PolicyOption).where(
                    PolicyOption.policy_id == policy.id,
                    PolicyOption.code == code,
                )
            )

            if policy_option is None:
                policy_option = PolicyOption(
                    policy_id=policy.id,
                    code=code,
                    name=name,
                    selected=selected,
                    variant=variant,
                    premium_amount=premium_amount,
                    currency=currency,
                    parameters=parameters,
                )

                db.add(policy_option)

                print(
                    f"Created policy option: "
                    f"{code}"
                )

            else:
                print(
                    f"Policy option already exists: "
                    f"{code}"
                )
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