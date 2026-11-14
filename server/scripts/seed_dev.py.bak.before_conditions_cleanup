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
from app.models.policy_document import PolicyDocument
from app.models.knowledge_document import (
    DocumentStatus,
    KnowledgeDocument,
)
from app.models.document_chunk import DocumentChunk
from app.models.conversation import Conversation
from app.models.message import Message, ConversationRole
from app.models.message_source import MessageSource
from app.models.ai_run import AiRun

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
        # POLICY DOCUMENTS
        # =====================================================

        policy_documents_data = [
            (
                "SIGNED_CONTRACT",
                "TI-2026-0001-contract.pdf",
                "dev://policies/TI-2026-0001/contract.pdf",
                True,
            ),
            (
                "ASSISTANCE_CARD",
                "TI-2026-0001-assistance-card.pdf",
                "dev://policies/TI-2026-0001/assistance-card.pdf",
                True,
            ),
        ]

        for (
                document_type,
                file_name,
                storage_uri,
                contains_pii,
        ) in policy_documents_data:

            policy_document = db.scalar(
                select(PolicyDocument).where(
                    PolicyDocument.policy_id == policy.id,
                    PolicyDocument.document_type == document_type,
                )
            )

            if policy_document is None:
                policy_document = PolicyDocument(
                    policy_id=policy.id,
                    document_type=document_type,
                    file_name=file_name,
                    storage_uri=storage_uri,
                    checksum=None,
                    contains_pii=contains_pii,
                )

                db.add(policy_document)

                print(
                    f"Created policy document: {document_type}"
                )

            else:
                print(
                    f"Policy document already exists: {document_type}"
                )

        # =====================================================
        # KNOWLEDGE DOCUMENTS
        # =====================================================

        knowledge_documents_data = [
            (
                "Travel Insurance Conditions 2026",
                "VPP",
                "2026.1",
                "cs",
                date(2026, 1, 1),
                date(2026, 12, 31),
                1,
                "travel-insurance-vpp-2026.pdf",
                "dev://knowledge/travel-insurance-vpp-2026.pdf",
            ),
            (
                "Travel Insurance Product Information 2026",
                "PRODUCT_INFORMATION",
                "2026.1",
                "cs",
                date(2026, 1, 1),
                date(2026, 12, 31),
                2,
                "travel-insurance-product-info-2026.pdf",
                "dev://knowledge/travel-insurance-product-info-2026.pdf",
            ),
        ]

        for (
                title,
                document_type,
                version,
                language,
                effective_from,
                effective_to,
                authority_rank,
                file_name,
                storage_uri,
        ) in knowledge_documents_data:

            knowledge_document = db.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.product_version_id == product_version.id,
                    KnowledgeDocument.document_type == document_type,
                    KnowledgeDocument.version == version,
                )
            )

            if knowledge_document is None:
                knowledge_document = KnowledgeDocument(
                    product_version_id=product_version.id,
                    title=title,
                    document_type=document_type,
                    version=version,
                    language=language,
                    effective_from=effective_from,
                    effective_to=effective_to,
                    authority_rank=authority_rank,
                    file_name=file_name,
                    storage_uri=storage_uri,
                    source_url=None,
                    checksum=None,
                    ingestion_status=DocumentStatus.READY,
                )

                db.add(knowledge_document)

                print(
                    f"Created knowledge document: {document_type}"
                )

            else:
                print(
                    f"Knowledge document already exists: {document_type}"
                )

        db.flush()

        # =====================================================
        # DOCUMENT CHUNKS
        # =====================================================

        knowledge_document = db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.product_version_id == product_version.id,
                KnowledgeDocument.document_type == "VPP",
                KnowledgeDocument.version == "2026.1",
            )
        )

        if knowledge_document is None:
            raise RuntimeError("VPP knowledge document was not found.")

        document_chunks_data = [
            (
                0,
                1,
                "1",
                "Medical Expenses",
                "MEDICAL_EXPENSES",
                "Medical expenses during an insured trip are covered according to the policy conditions.",
            ),
            (
                1,
                5,
                "5",
                "Baggage",
                "BAGGAGE",
                "Baggage insurance covers eligible loss, damage or destruction of insured baggage.",
            ),
            (
                2,
                8,
                "8",
                "Liability",
                "LIABILITY",
                "Liability insurance covers eligible damage caused by the insured person to another person.",
            ),
        ]

        for (
                chunk_index,
                page_number,
                article_number,
                section_title,
                coverage_code,
                content,
        ) in document_chunks_data:

            document_chunk = db.scalar(
                select(DocumentChunk).where(
                    DocumentChunk.document_id == knowledge_document.id,
                    DocumentChunk.chunk_index == chunk_index,
                )
            )

            if document_chunk is None:
                document_chunk = DocumentChunk(
                    document_id=knowledge_document.id,
                    chunk_index=chunk_index,
                    page_number=page_number,
                    article_number=article_number,
                    section_title=section_title,
                    section_path=None,
                    coverage_code=coverage_code,
                    content=content,

                    # embeddings will be generated later
                    embedding=None,

                    chunk_metadata={
                        "source": "synthetic_dev_seed",
                    },
                )

                db.add(document_chunk)

                print(
                    f"Created document chunk: "
                    f"{chunk_index} -> {coverage_code}"
                )

            else:
                print(
                    f"Document chunk already exists: "
                    f"{chunk_index}"
                )
        # =====================================================
        # CONVERSATION
        # =====================================================

        conversation = db.scalar(
            select(Conversation).where(
                Conversation.user_id == user.id,
                Conversation.policy_id == policy.id,
                Conversation.title == "Travel insurance test chat",
            )
        )

        if conversation is None:
            conversation = Conversation(
                user_id=user.id,
                policy_id=policy.id,
                title="Travel insurance test chat",
            )

            db.add(conversation)
            db.flush()

            print("Created conversation.")

        else:
            print("Conversation already exists.")


        # =====================================================
        # MESSAGES
        # =====================================================

        user_message_content = (
            "Is my baggage covered and what is the limit?"
        )

        user_message = db.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.role == ConversationRole.USER,
                Message.content == user_message_content,
            )
        )

        if user_message is None:
            user_message = Message(
                conversation_id=conversation.id,
                role=ConversationRole.USER,
                content=user_message_content,
            )

            db.add(user_message)

            print("Created user message.")

        else:
            print("User message already exists.")


        assistant_message_content = (
            "Yes. Your policy includes baggage coverage "
            "with a limit of 100,000 CZK."
        )

        assistant_message = db.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.role == ConversationRole.ASSISTANT,
                Message.content == assistant_message_content,
            )
        )

        if assistant_message is None:
            assistant_message = Message(
                conversation_id=conversation.id,
                role=ConversationRole.ASSISTANT,
                content=assistant_message_content,
            )

            db.add(assistant_message)

            print("Created assistant message.")

        else:
            print("Assistant message already exists.")

        db.flush()


        # =====================================================
        # MESSAGE SOURCES
        # =====================================================

        baggage_coverage_type = db.scalar(
            select(CoverageType).where(
                CoverageType.code == "BAGGAGE"
            )
        )

        if baggage_coverage_type is None:
            raise RuntimeError(
                "BAGGAGE coverage type was not found."
            )


        baggage_policy_coverage = db.scalar(
            select(PolicyCoverage).where(
                PolicyCoverage.policy_id == policy.id,
                PolicyCoverage.coverage_type_id
                == baggage_coverage_type.id,
            )
        )

        if baggage_policy_coverage is None:
            raise RuntimeError(
                "BAGGAGE policy coverage was not found."
            )


        baggage_chunk = db.scalar(
            select(DocumentChunk).where(
                DocumentChunk.document_id == knowledge_document.id,
                DocumentChunk.coverage_code == "BAGGAGE",
            )
        )

        if baggage_chunk is None:
            raise RuntimeError(
                "BAGGAGE document chunk was not found."
            )


        policy_coverage_source = db.scalar(
            select(MessageSource).where(
                MessageSource.message_id == assistant_message.id,
                MessageSource.source_type == "POLICY_COVERAGE",
                MessageSource.policy_coverage_id
                == baggage_policy_coverage.id,
            )
        )

        if policy_coverage_source is None:
            policy_coverage_source = MessageSource(
                message_id=assistant_message.id,
                source_type="POLICY_COVERAGE",
                document_chunk_id=None,
                policy_coverage_id=baggage_policy_coverage.id,
                policy_option_id=None,
                relevance_score=Decimal("1.0"),
            )

            db.add(policy_coverage_source)

            print("Created POLICY_COVERAGE message source.")

        else:
            print("POLICY_COVERAGE message source already exists.")


        document_chunk_source = db.scalar(
            select(MessageSource).where(
                MessageSource.message_id == assistant_message.id,
                MessageSource.source_type == "DOCUMENT_CHUNK",
                MessageSource.document_chunk_id == baggage_chunk.id,
            )
        )

        if document_chunk_source is None:
            document_chunk_source = MessageSource(
                message_id=assistant_message.id,
                source_type="DOCUMENT_CHUNK",
                document_chunk_id=baggage_chunk.id,
                policy_coverage_id=None,
                policy_option_id=None,
                relevance_score=Decimal("0.92"),
            )

            db.add(document_chunk_source)

            print("Created DOCUMENT_CHUNK message source.")

        else:
            print("DOCUMENT_CHUNK message source already exists.")


        # =====================================================
        # AI RUN
        # =====================================================

        ai_run = db.scalar(
            select(AiRun).where(
                AiRun.message_id == assistant_message.id,
                AiRun.prompt_version == "dev-v1",
            )
        )

        if ai_run is None:
            ai_run = AiRun(
                conversation_id=conversation.id,
                message_id=assistant_message.id,

                # Synthetic dev data — no real LLM call happened.
                model_provider="SYNTHETIC",
                model_name="dev-test-model",
                prompt_version="dev-v1",

                input_tokens=120,
                output_tokens=45,

                latency_ms=850,
                retrieval_count=2,

                safety_result="PASSED",
            )

            db.add(ai_run)

            print("Created AI run.")

        else:
            print("AI run already exists.")
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