from __future__ import annotations

from dataclasses import dataclass

from core.analytics.models import MetricFactView
from core.errors import AppError, ErrorCode


@dataclass(frozen=True)
class MetricSpec:
    metric_id: str
    display_name: str
    visibility_scope: str
    allowed_granularities: tuple[str, ...]
    allowed_dimension_keys: tuple[tuple[str, ...], ...]


METRIC_CATALOG_V1: dict[str, MetricSpec] = {
    "yt.channel.subscribers_total": MetricSpec("yt.channel.subscribers_total", "Inscritos totais", "private_authorized", ("snapshot",), ((),)),
    "yt.video.public_views": MetricSpec("yt.video.public_views", "Visualizacoes publicas", "public_snapshot", ("snapshot",), ((),)),
    "yt.video.public_likes": MetricSpec("yt.video.public_likes", "Likes publicos", "public_snapshot", ("snapshot",), ((),)),
    "yt.video.public_comments": MetricSpec("yt.video.public_comments", "Comentarios publicos", "public_snapshot", ("snapshot",), ((),)),
    "yt.analytics.views": MetricSpec("yt.analytics.views", "Views consolidadas", "private_authorized", ("day", "period_total"), ((), ("country",), ("traffic_source",))),
    "yt.analytics.watch_time_minutes": MetricSpec("yt.analytics.watch_time_minutes", "Tempo de exibicao (min)", "private_authorized", ("day", "period_total"), ((), ("country",), ("traffic_source",))),
    "yt.analytics.avg_view_duration_sec": MetricSpec("yt.analytics.avg_view_duration_sec", "Duracao media (s)", "private_authorized", ("day", "period_total"), ((),)),
    "yt.analytics.avg_view_percentage": MetricSpec("yt.analytics.avg_view_percentage", "Percentual medio assistido", "private_authorized", ("day", "period_total"), ((),)),
    "yt.analytics.subscribers_gained": MetricSpec("yt.analytics.subscribers_gained", "Inscritos ganhos", "private_authorized", ("day", "period_total"), ((),)),
    "yt.analytics.subscribers_lost": MetricSpec("yt.analytics.subscribers_lost", "Inscritos perdidos", "private_authorized", ("day", "period_total"), ((),)),
    "yt.analytics.impressions": MetricSpec("yt.analytics.impressions", "Impressoes", "private_authorized", ("day", "period_total"), ((),)),
    "yt.analytics.impressions_ctr": MetricSpec("yt.analytics.impressions_ctr", "CTR de impressoes (%)", "private_authorized", ("day", "period_total"), ((),)),
    "yt.analytics.retention_curve": MetricSpec("yt.analytics.retention_curve", "Curva de retencao", "private_authorized", ("curve_100",), (("audience_type",),)),
    "yt.analytics.traffic_sources": MetricSpec("yt.analytics.traffic_sources", "Fontes de trafego", "private_authorized", ("period_total",), (("traffic_source_type",),)),
}


def validate_metric_fact_spec(metric_id: str, granularity: str, dimensions: dict[str, str], visibility_scope: str) -> MetricSpec:
    spec = METRIC_CATALOG_V1.get(metric_id)
    if spec is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, f"Metrica desconhecida no catalogo v1: {metric_id}.", http_status=422)
    if spec.visibility_scope != visibility_scope and metric_id != "yt.video.public_views":
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"Escopo {visibility_scope} incompativel para {metric_id} (esperado {spec.visibility_scope}).",
            http_status=422,
        )
    if granularity not in spec.allowed_granularities:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"Granularidade '{granularity}' invalida para {metric_id}.",
            http_status=422,
        )
    dim_keys = tuple(sorted(dimensions.keys()))
    if dim_keys not in spec.allowed_dimension_keys:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"Combinacao de dimensoes {dim_keys} nao suportada para {metric_id}.",
            http_status=422,
        )
    return spec


def assert_compatible_comparison(items: list[MetricFactView]) -> None:
    """Enforces AN-006: prevents comparing incompatible metrics, granularities, scopes, or dimensions."""
    if len(items) < 2:
        return
    base = items[0]
    for other in items[1:]:
        if other.metric_id != base.metric_id:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                f"Comparacao incompativel: metricas distintas ({base.metric_id} vs {other.metric_id}).",
                http_status=422,
                details={"next_action": "Selecione a mesma metrica para comparar."},
            )
        if other.granularity != base.granularity:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                f"Comparacao incompativel: granularidades distintas ({base.granularity} vs {other.granularity}).",
                http_status=422,
            )
        if other.visibility_scope != base.visibility_scope:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Comparacao incompativel: nao misture dado publico com analytics privado.",
                http_status=422,
            )
        if sorted(other.dimensions_json.keys()) != sorted(base.dimensions_json.keys()):
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Comparacao incompativel: dimensoes distintas entre os itens.",
                http_status=422,
            )
