"""Validação de parâmetros e tipos de erro do motor geométrico."""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from app.core.box_parameters import (
    FIELD_LABELS,
    FINGER_COUNT_LIMITS,
    LIMITS,
    BoxParameters,
    BoxType,
    DimensionMode,
    JointType,
)


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ValidationIssue:
    severity: Severity
    field: str
    message: str


class GeometryError(ValueError):
    """Geometria inviável ou parâmetros incompatíveis (mensagem em português)."""

    def __init__(self, message: str, field: str = "geometria") -> None:
        super().__init__(message)
        self.issue = ValidationIssue(Severity.ERROR, field, message)


def has_errors(issues) -> bool:
    return any(i.severity is Severity.ERROR for i in issues)


def parse_number(text: str) -> float:
    """Converte texto em float aceitando vírgula decimal.

    Pode devolver NaN/inf (ex.: "nan"); quem valida é `validate_parameters`.
    """
    cleaned = text.strip().replace(" ", "")
    if not cleaned:
        raise ValueError("campo vazio")
    if "," in cleaned and "." in cleaned:
        raise ValueError("use apenas um separador decimal")
    return float(cleaned.replace(",", "."))


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_parameters(p: BoxParameters) -> list[ValidationIssue]:
    """Valida tipos, finitude e limites. Não avalia a viabilidade geométrica."""
    issues: list[ValidationIssue] = []

    def err(field: str, msg: str) -> None:
        issues.append(ValidationIssue(Severity.ERROR, field, msg))

    for name, (lo, hi) in LIMITS.items():
        label = FIELD_LABELS[name]
        value = getattr(p, name)
        if not _is_number(value) or not math.isfinite(value):
            err(name, f"{label}: informe um número finito (NaN e infinito não são aceitos).")
            continue
        if name in ("clearance", "kerf"):
            if value < 0:
                err(name, f"{label}: não pode ser negativo.")
                continue
        elif value <= 0:
            err(name, f"{label}: deve ser maior que zero.")
            continue
        if value < lo or value > hi:
            err(name, f"{label}: deve estar entre {lo:g} e {hi:g} mm (recebido {value:g}).")

    if not isinstance(p.dimension_mode, DimensionMode):
        err("dimension_mode", "Modo de dimensionamento inválido.")
    if not isinstance(p.box_type, BoxType):
        err("box_type", "Tipo de caixa inválido (use aberta ou fechada).")
    if not isinstance(p.joint_type, JointType):
        err("joint_type", "Tipo de união inválido (apenas finger joint é suportado).")

    fc = p.finger_count
    if fc is not None:
        lo, hi = FINGER_COUNT_LIMITS
        if not isinstance(fc, int) or isinstance(fc, bool):
            err("finger_count", "Número de dedos: informe um número inteiro.")
        elif fc < lo or fc > hi:
            err("finger_count", f"Número de dedos: deve estar entre {lo} e {hi}.")
        elif fc % 2 == 0:
            err("finger_count",
                "Número de dedos: use um valor ímpar (3, 5, 7, ...) para que as "
                "extremidades da junta fiquem simétricas.")
    return issues
