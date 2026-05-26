"""Virtuelle Bankkonten – Fahrer & Spedition."""

from __future__ import annotations

from sqlalchemy.orm import Session

from server import models

USER_START_BALANCE = 5_000.0
SPEDITION_START_BALANCE = 25_000.0
SPEDITION_REVENUE_SHARE = 0.15


def ensure_user_bank(db: Session, user_id: int) -> models.BankAccount:
    acc = db.query(models.BankAccount).filter(models.BankAccount.user_id == user_id).first()
    if not acc:
        acc = models.BankAccount(user_id=user_id, balance_eur=USER_START_BALANCE)
        db.add(acc)
        db.flush()
    return acc


def ensure_spedition_bank(db: Session, spedition_id: int) -> models.BankAccount:
    acc = (
        db.query(models.BankAccount)
        .filter(models.BankAccount.spedition_id == spedition_id)
        .first()
    )
    if not acc:
        acc = models.BankAccount(
            spedition_id=spedition_id, balance_eur=SPEDITION_START_BALANCE
        )
        db.add(acc)
        db.flush()
    return acc


def credit_trip_revenue(
    db: Session, user_id: int, spedition_id: int | None, revenue_eur: float
) -> None:
    if revenue_eur <= 0:
        return
    user_acc = ensure_user_bank(db, user_id)
    user_acc.balance_eur += revenue_eur
    if spedition_id:
        sp_acc = ensure_spedition_bank(db, spedition_id)
        sp_acc.balance_eur += revenue_eur * SPEDITION_REVENUE_SHARE
