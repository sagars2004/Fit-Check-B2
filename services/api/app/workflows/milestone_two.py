from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from itertools import product
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import FitCheckError
from app.db.models import (
    Garment,
    GarmentAsset,
    GarmentEvidence,
    OutfitItem,
    OutfitPlan,
    User,
    WearEvent,
    new_id,
)
from app.domain.enums import GarmentStatus, OutfitStatus
from app.domain.schemas import (
    OutfitItemResponse,
    OutfitPlanResponse,
    OutfitRecommendationResponse,
    OutfitRecommendRequest,
    WearEventResponse,
    WearRequest,
    WeatherSnapshotResponse,
)
from app.services.storage import ObjectStorage
from app.services.weather import WeatherClient, WeatherSnapshot

_OUTERWEAR_TERMS = ("coat", "jacket", "blazer", "outerwear", "raincoat", "parka")
_BOTTOM_TERMS = ("bottom", "pants", "trouser", "jeans", "shorts", "skirt", "legging")
_ONE_PIECE_TERMS = ("dress", "jumpsuit", "romper")
_SHOE_TERMS = ("shoe", "boot", "sneaker", "loafer", "sandal", "heel", "footwear")
_ACCESSORY_TERMS = ("accessory", "bag", "scarf", "hat", "belt", "jewelry")
_NEUTRAL_COLORS = {
    "black",
    "white",
    "gray",
    "grey",
    "navy",
    "beige",
    "cream",
    "brown",
    "tan",
    "khaki",
    "olive",
    "denim",
}


@dataclass(frozen=True)
class _PlannedOutfit:
    items: tuple[tuple[str, Garment], ...]
    score: float
    reasoning: str

    @property
    def primary_ids(self) -> frozenset[str]:
        return frozenset(
            garment.id for role, garment in self.items if role in {"top", "bottom", "one_piece"}
        )


class MilestoneTwoWorkflow:
    """Rule-first planner that only persists and returns owned approved garments."""

    def __init__(self, settings: Settings, storage: ObjectStorage, weather: WeatherClient) -> None:
        self.settings = settings
        self.storage = storage
        self.weather = weather

    async def recommend(
        self, session: AsyncSession, payload: OutfitRecommendRequest
    ) -> OutfitRecommendationResponse:
        user = await self._ensure_demo_user(session)
        requested_location = payload.location or user.default_location or "New York, NY"
        weather = await self.weather.forecast(requested_location, payload.forecast_date)
        garments = await self._approved_garments(session, user.id)
        recently_worn = await self._recently_worn_garment_ids(
            session, user.id, payload.forecast_date
        )
        planned, warnings = _build_outfits(
            garments,
            weather,
            payload.occasion,
            recently_worn,
            utilization_mode=payload.utilization_mode,
        )
        if not planned:
            raise FitCheckError(
                "INSUFFICIENT_APPROVED_GARMENTS",
                (
                    "Fit Check needs an approved top and bottom, or an approved dress/jumpsuit, "
                    "to build a look."
                ),
                recommended_action="Approve more source-backed wardrobe items, then try again.",
            )

        plans: list[OutfitPlan] = []
        for candidate in planned:
            plan = OutfitPlan(
                id=new_id(),
                user_id=user.id,
                weather_snapshot=weather.as_dict(),
                occasion=payload.occasion.strip(),
                score=round(candidate.score, 3),
                reasoning=candidate.reasoning,
                status=OutfitStatus.PROPOSED.value,
                planner_run_id=f"local-outfit-planner-{new_id()}",
            )
            session.add(plan)
            await session.flush()
            for role, garment in candidate.items:
                session.add(
                    OutfitItem(id=new_id(), outfit_id=plan.id, garment_id=garment.id, role=role)
                )
            plans.append(plan)
        await session.commit()
        return OutfitRecommendationResponse(
            weather=_weather_response(weather),
            occasion=payload.occasion.strip(),
            options=[await self._plan_response(session, plan) for plan in plans],
            warnings=warnings,
        )

    async def list_outfits(
        self, session: AsyncSession, status: str | None = None
    ) -> list[OutfitPlanResponse]:
        user = await self._ensure_demo_user(session)
        statement = (
            select(OutfitPlan)
            .where(OutfitPlan.user_id == user.id)
            .order_by(OutfitPlan.created_at.desc())
        )
        if status:
            statement = statement.where(OutfitPlan.status == status)
        plans = list((await session.scalars(statement)).all())
        return [await self._plan_response(session, plan) for plan in plans]

    async def save_outfit(self, session: AsyncSession, outfit_id: str) -> OutfitPlanResponse:
        user = await self._ensure_demo_user(session)
        plan = await self._owned_plan(session, user.id, outfit_id)
        if plan.status != OutfitStatus.WORN.value:
            plan.status = OutfitStatus.SAVED.value
            await session.commit()
        return await self._plan_response(session, plan)

    async def record_wear(
        self, session: AsyncSession, outfit_id: str, payload: WearRequest
    ) -> WearEventResponse:
        user = await self._ensure_demo_user(session)
        plan = await self._owned_plan(session, user.id, outfit_id)
        item_rows = [
            (item, garment)
            for item, garment in (
                await session.execute(
                    select(OutfitItem, Garment)
                    .join(Garment, OutfitItem.garment_id == Garment.id)
                    .where(OutfitItem.outfit_id == plan.id)
                )
            ).tuples()
        ]
        if not item_rows:
            raise FitCheckError("OUTFIT_EMPTY", "This look has no garments to record.")

        if payload.action == "wear":
            existing = await session.scalar(
                select(WearEvent).where(
                    WearEvent.user_id == user.id,
                    WearEvent.outfit_id == plan.id,
                    WearEvent.worn_on == payload.worn_on,
                    WearEvent.reversed_at.is_(None),
                )
            )
            event: WearEvent
            if existing is None:
                event = WearEvent(
                    id=new_id(),
                    user_id=user.id,
                    outfit_id=plan.id,
                    worn_on=payload.worn_on,
                    notes=payload.notes,
                )
                session.add(event)
                for _, garment in item_rows:
                    garment.wear_count += 1
            else:
                assert existing is not None
                event = existing
            plan.status = OutfitStatus.WORN.value
            await session.commit()
            return _wear_response(event, plan, "wear", item_rows)

        event_to_undo = await session.scalar(
            select(WearEvent)
            .where(
                WearEvent.user_id == user.id,
                WearEvent.outfit_id == plan.id,
                WearEvent.worn_on == payload.worn_on,
                WearEvent.reversed_at.is_(None),
            )
            .order_by(WearEvent.created_at.desc())
        )
        if event_to_undo is None:
            raise FitCheckError(
                "WEAR_EVENT_NOT_FOUND",
                "There is no active wear record for this look on that date.",
                recommended_action="Choose the date you marked this look as worn.",
            )
        event_to_undo.reversed_at = datetime.now(UTC)
        event_to_undo.reversal_reason = payload.notes or "Reversed by wardrobe owner."
        for _, garment in item_rows:
            garment.wear_count = max(0, garment.wear_count - 1)
        plan.status = OutfitStatus.SAVED.value
        await session.commit()
        return _wear_response(event_to_undo, plan, "undo", item_rows)

    async def _approved_garments(self, session: AsyncSession, user_id: str) -> list[Garment]:
        return list(
            (
                await session.scalars(
                    select(Garment)
                    .where(
                        Garment.user_id == user_id,
                        Garment.status == GarmentStatus.APPROVED.value,
                        Garment.archived_at.is_(None),
                        Garment.deleted_at.is_(None),
                    )
                    .order_by(Garment.created_at.asc())
                )
            ).all()
        )

    async def _recently_worn_garment_ids(
        self, session: AsyncSession, user_id: str, forecast_date: date
    ) -> set[str]:
        since = forecast_date - timedelta(days=7)
        rows = await session.scalars(
            select(OutfitItem.garment_id)
            .join(OutfitPlan, OutfitItem.outfit_id == OutfitPlan.id)
            .join(WearEvent, WearEvent.outfit_id == OutfitPlan.id)
            .where(
                WearEvent.user_id == user_id,
                WearEvent.reversed_at.is_(None),
                WearEvent.worn_on >= since,
                WearEvent.worn_on <= forecast_date,
            )
        )
        return set(rows.all())

    async def _owned_plan(self, session: AsyncSession, user_id: str, outfit_id: str) -> OutfitPlan:
        plan = await session.scalar(
            select(OutfitPlan).where(OutfitPlan.id == outfit_id, OutfitPlan.user_id == user_id)
        )
        if plan is None:
            raise FitCheckError(
                "OUTFIT_NOT_FOUND", "That look is unavailable.", entity_id=outfit_id
            )
        return plan

    async def _plan_response(self, session: AsyncSession, plan: OutfitPlan) -> OutfitPlanResponse:
        rows = [
            (item, garment)
            for item, garment in (
                await session.execute(
                    select(OutfitItem, Garment)
                    .join(Garment, OutfitItem.garment_id == Garment.id)
                    .where(OutfitItem.outfit_id == plan.id)
                    .order_by(OutfitItem.created_at.asc())
                )
            ).tuples()
        ]
        weather = WeatherSnapshot.from_dict(dict(plan.weather_snapshot))
        items = [await self._outfit_item_response(session, item, garment) for item, garment in rows]
        return OutfitPlanResponse(
            id=plan.id,
            title=_outfit_title(items),
            weather=_weather_response(weather),
            occasion=plan.occasion,
            score=float(plan.score),
            reasoning=plan.reasoning,
            status=plan.status,
            planner_run_id=plan.planner_run_id,
            items=items,
            created_at=plan.created_at,
        )

    async def _outfit_item_response(
        self, session: AsyncSession, item: OutfitItem, garment: Garment
    ) -> OutfitItemResponse:
        image_url: str | None = None
        if garment.canonical_asset_id:
            asset = await session.scalar(
                select(GarmentAsset).where(
                    GarmentAsset.id == garment.canonical_asset_id,
                    GarmentAsset.qa_status == "approved",
                )
            )
            if asset is not None:
                image_url = await self.storage.signed_read_url(asset.object_key)
        if image_url is None:
            evidence = await session.scalar(
                select(GarmentEvidence)
                .where(GarmentEvidence.garment_id == garment.id)
                .order_by(GarmentEvidence.created_at.asc())
            )
            if evidence is not None:
                image_url = await self.storage.signed_read_url(evidence.crop_key)
        return OutfitItemResponse(
            garment_id=garment.id,
            role=item.role,
            name=garment.name,
            category=garment.category,
            colors=list(garment.colors),
            tags=list(garment.tags),
            wear_count=garment.wear_count,
            price=float(garment.price) if garment.price is not None else None,
            cost_per_wear=_cost_per_wear(garment),
            evidence_status=garment.evidence_status,
            image_url=image_url,
        )

    async def _ensure_demo_user(self, session: AsyncSession) -> User:
        user = await session.scalar(select(User).where(User.id == self.settings.demo_user_id))
        if user is not None:
            return user
        user = User(
            id=self.settings.demo_user_id,
            auth_subject="demo:local-owner",
            display_name="Fit Check local owner",
            default_location="New York, NY",
        )
        session.add(user)
        await session.flush()
        return user


def _build_outfits(
    garments: list[Garment],
    weather: WeatherSnapshot,
    occasion: str,
    recently_worn: set[str],
    *,
    utilization_mode: bool,
) -> tuple[list[_PlannedOutfit], list[str]]:
    groups: dict[str, list[Garment]] = {
        "top": [],
        "bottom": [],
        "one_piece": [],
        "outerwear": [],
        "footwear": [],
        "accessory": [],
    }
    for garment in garments:
        group = _category_group(garment.category)
        if group:
            groups[group].append(garment)

    if not (groups["one_piece"] or (groups["top"] and groups["bottom"])):
        return [], []

    needs_outerwear = weather.low_c < 12 or weather.precipitation_probability >= 40
    options: list[_PlannedOutfit] = []
    primary_sets: list[tuple[tuple[str, Garment], ...]] = []
    primary_sets.extend((("one_piece", garment),) for garment in groups["one_piece"])
    primary_sets.extend(
        (("top", top), ("bottom", bottom))
        for top, bottom in product(groups["top"], groups["bottom"])
    )

    for primary in primary_sets:
        if _weather_disqualifies(primary, weather):
            continue
        outer_options: list[Garment | None] = [None]
        if groups["outerwear"]:
            outer_options = list(groups["outerwear"])
            if not needs_outerwear:
                outer_options = [None, *outer_options]
        shoe_options: list[Garment | None] = [None]
        if groups["footwear"]:
            shoe_options = list(groups["footwear"])
        accessory_options: list[Garment | None] = [None]
        if groups["accessory"] and (weather.low_c < 10 or "dinner" in occasion.casefold()):
            accessory_options = [None, groups["accessory"][0]]
        for outerwear, shoe, accessory in product(outer_options, shoe_options, accessory_options):
            entries = list(primary)
            if outerwear is not None:
                entries.append(("outerwear", outerwear))
            if shoe is not None:
                entries.append(("footwear", shoe))
            if accessory is not None:
                entries.append(("accessory", accessory))
            score = _score_outfit(entries, weather, occasion, recently_worn, utilization_mode)
            options.append(
                _PlannedOutfit(
                    items=tuple(entries),
                    score=score,
                    reasoning=_reasoning(entries, weather, occasion, needs_outerwear),
                )
            )

    options.sort(
        key=lambda option: (-option.score, tuple(garment.id for _, garment in option.items))
    )
    selected: list[_PlannedOutfit] = []
    for option in options:
        if any(option.primary_ids == existing.primary_ids for existing in selected):
            continue
        selected.append(option)
        if len(selected) == 3:
            break

    warnings: list[str] = []
    if needs_outerwear and not groups["outerwear"]:
        warnings.append(
            "Rain or cooler temperatures suggest a layer, but no approved outerwear is cataloged."
        )
    if not groups["footwear"]:
        warnings.append("No approved footwear is cataloged, so these looks omit shoes.")
    if len(selected) < 3:
        look_count = "look is" if len(selected) == 1 else "looks are"
        warnings.append(
            f"Only {len(selected)} materially different owned {look_count} available. "
            "Add approved wardrobe items for more variety."
        )
    return selected, warnings


def _category_group(category: str) -> str | None:
    normalized = category.casefold()
    if any(term in normalized for term in _ONE_PIECE_TERMS):
        return "one_piece"
    if any(term in normalized for term in _OUTERWEAR_TERMS):
        return "outerwear"
    if any(term in normalized for term in _BOTTOM_TERMS):
        return "bottom"
    if any(term in normalized for term in _SHOE_TERMS):
        return "footwear"
    if any(term in normalized for term in _ACCESSORY_TERMS):
        return "accessory"
    if normalized in {"top", "shirt", "tee", "t-shirt", "blouse", "sweater", "knit", "hoodie"}:
        return "top"
    return None


def _weather_disqualifies(
    entries: tuple[tuple[str, Garment], ...], weather: WeatherSnapshot
) -> bool:
    for role, garment in entries:
        if role != "bottom":
            continue
        category = garment.category.casefold()
        if "short" in category and (weather.high_c < 18 or weather.precipitation_probability >= 40):
            return True
    return False


def _score_outfit(
    entries: list[tuple[str, Garment]],
    weather: WeatherSnapshot,
    occasion: str,
    recently_worn: set[str],
    utilization_mode: bool,
) -> float:
    score = 100.0
    colors: list[str] = []
    occasion_terms = occasion.casefold()
    for role, garment in entries:
        tags = {tag.casefold() for tag in garment.tags}
        seasons = {season.casefold() for season in garment.seasons}
        colors.extend(color.casefold() for color in garment.colors)
        if garment.id in recently_worn:
            score -= 18
        score -= min(garment.wear_count, 12) * 0.7
        if utilization_mode:
            score += min(8.0, 8.0 / (garment.wear_count + 1))
        if weather.low_c < 12 and ({"winter", "cold", "warm"} & (tags | seasons)):
            score += 8
        if weather.high_c >= 20 and ({"summer", "lightweight", "breathable"} & (tags | seasons)):
            score += 6
        if any(term in occasion_terms for term in ("work", "office", "commute")) and (
            {"work", "office", "smart", "formal"} & tags or "blazer" in garment.category.casefold()
        ):
            score += 8
        if any(term in occasion_terms for term in ("dinner", "evening", "date")) and (
            {"evening", "dressy", "dinner"} & tags or role == "one_piece"
        ):
            score += 7
        if any(term in occasion_terms for term in ("casual", "weekend", "errand")) and (
            {"casual", "weekend", "comfortable"} & tags
        ):
            score += 6
    score += _palette_score(colors)
    if weather.precipitation_probability >= 40 and any(role == "outerwear" for role, _ in entries):
        score += 12
    if weather.low_c < 12 and any(role == "outerwear" for role, _ in entries):
        score += 8
    return score


def _palette_score(colors: list[str]) -> float:
    if not colors:
        return 0.0
    unique = set(colors)
    neutrals = unique & _NEUTRAL_COLORS
    if len(unique) == 1:
        return 6.0
    if neutrals:
        return 5.0
    if len(unique) == 2:
        return 2.0
    return -3.0


def _reasoning(
    entries: list[tuple[str, Garment]],
    weather: WeatherSnapshot,
    occasion: str,
    needs_outerwear: bool,
) -> str:
    primary_names = [
        garment.name for role, garment in entries if role in {"top", "bottom", "one_piece"}
    ]
    detail = f"{weather.condition.title()} {weather.low_c:.0f}–{weather.high_c:.0f}°C"
    if weather.precipitation_probability >= 40:
        detail += f" with a {weather.precipitation_probability}% chance of precipitation"
    description = f"{detail} suits {' + '.join(primary_names)} for {occasion.strip()}."
    if needs_outerwear:
        outerwear = next((garment.name for role, garment in entries if role == "outerwear"), None)
        description += (
            f" {outerwear} adds a practical weather layer."
            if outerwear
            else " No approved outerwear is available, so consider a layer outside this catalog."
        )
    colors = [color for _, garment in entries for color in garment.colors]
    if colors:
        description += f" Palette: {', '.join(colors[:3])}."
    return description


def _weather_response(weather: WeatherSnapshot) -> WeatherSnapshotResponse:
    return WeatherSnapshotResponse(**weather.as_dict())


def _outfit_title(items: list[OutfitItemResponse]) -> str:
    primary = [item.name for item in items if item.role in {"top", "bottom", "one_piece"}]
    return " + ".join(primary) if primary else "Owned wardrobe look"


def _wear_response(
    event: WearEvent,
    plan: OutfitPlan,
    action: Literal["wear", "undo"],
    item_rows: list[tuple[OutfitItem, Garment]],
) -> WearEventResponse:
    return WearEventResponse(
        event_id=event.id,
        outfit_id=plan.id,
        action=action,
        worn_on=event.worn_on,
        outfit_status=plan.status,
        garment_wear_counts={garment.id: garment.wear_count for _, garment in item_rows},
        garment_cost_per_wear={garment.id: _cost_per_wear(garment) for _, garment in item_rows},
    )


def _cost_per_wear(garment: Garment) -> float | None:
    if garment.price is None or garment.wear_count <= 0:
        return None
    return round(float(garment.price) / garment.wear_count, 2)
