from datetime import datetime, timedelta
import random

from flask import Blueprint, jsonify, request

from database.database import db
from database.models import User
from database.api_models import APIKey, APIUsage
from database.zentra_models import (
    ZentraPlayer,
    ZentraMarriage,
    ZentraTransaction,
)

api = Blueprint("api", __name__, url_prefix="/api/v1")


def daily_limit_for(user):
    plan = (user.plan or "FREE").upper()
    limits = {
        "OWNER": None,
        "ADMIN": None,
        "PRO": 5000,
        "PREMIUM": 1000,
        "PAID": 1000,
        "FREE": 100,
    }
    return limits.get(plan, 100)


def record_usage(api_key, status_code, endpoint="/api/v1/ping"):
    db.session.add(APIUsage(
        api_key_id=api_key.id,
        endpoint=endpoint[:120],
        status_code=status_code,
    ))
    db.session.commit()


def authenticate(endpoint):
    supplied_key = request.headers.get("X-API-Key", "").strip()

    if not supplied_key:
        return None, None, (jsonify(
            success=False, error="Missing X-API-Key header"
        ), 401)

    api_key = APIKey.query.filter_by(
        key=supplied_key, is_active=True
    ).first()

    if not api_key:
        return None, None, (jsonify(
            success=False, error="Invalid or revoked API key"
        ), 401)

    user = db.session.get(User, api_key.user_id)
    now = datetime.utcnow()

    if (
        not user
        or not user.is_active_user
        or (user.expires_at and user.expires_at <= now)
    ):
        record_usage(api_key, 403, endpoint)
        return None, None, (jsonify(
            success=False, error="Account inactive or expired"
        ), 403)

    since = now - timedelta(hours=24)
    limit = daily_limit_for(user)
    account_key_ids = db.session.query(APIKey.id).filter(
        APIKey.user_id == user.id
    )

    used = APIUsage.query.filter(
        APIUsage.api_key_id.in_(account_key_ids),
        APIUsage.created_at >= since,
        APIUsage.status_code == 200,
    ).count()

    if limit is not None and used >= limit:
        record_usage(api_key, 429, endpoint)
        return None, None, (jsonify(
            success=False,
            error="API usage limit reached",
            limit=limit,
            used=used,
        ), 429)

    return api_key, user, None


def get_player(platform_id, display_name):
    platform_id = str(platform_id or "").strip()
    display_name = str(display_name or "Player").strip()[:80] or "Player"

    if not platform_id or len(platform_id) > 120:
        raise ValueError("A valid sender_id is required.")

    player = ZentraPlayer.query.filter_by(
        platform_id=platform_id
    ).first()

    if player is None:
        player = ZentraPlayer(
            platform_id=platform_id,
            display_name=display_name,
            balance=500,
        )
        db.session.add(player)
        db.session.flush()
    else:
        player.display_name = display_name

    return player


def log_transaction(player, action, amount, other=None):
    db.session.add(ZentraTransaction(
        player_id=player.id,
        action=action,
        amount=amount,
        balance_after=player.balance,
        other_player_id=other.id if other else None,
    ))


@api.route("/ping", methods=["GET"])
def ping():
    endpoint = "/api/v1/ping"
    api_key, user, error = authenticate(endpoint)

    if error:
        return error

    now = datetime.utcnow()
    since = now - timedelta(hours=24)
    limit = daily_limit_for(user)
    key_ids = db.session.query(APIKey.id).filter(
        APIKey.user_id == user.id
    )
    used = APIUsage.query.filter(
        APIUsage.api_key_id.in_(key_ids),
        APIUsage.created_at >= since,
        APIUsage.status_code == 200,
    ).count()

    api_key.last_used = now
    record_usage(api_key, 200, endpoint)

    return jsonify(
        success=True,
        message="PRIME ZENITH API is online",
        plan=user.plan,
        usage_last_24_hours=used + 1,
        limit_last_24_hours=limit,
    ), 200


@api.route("/zentra/command", methods=["POST"])
def zentra_command():
    endpoint = "/api/v1/zentra/command"
    api_key, user, error = authenticate(endpoint)

    if error:
        return error

    data = request.get_json(silent=True) or {}
    sender_id = str(data.get("sender_id") or "").strip()
    sender_name = str(data.get("sender_name") or "Player").strip()[:80]
    command = str(data.get("command") or "").strip().lower().lstrip("!")
    target_id = str(data.get("target_id") or "").strip()
    target_name = str(data.get("target_name") or "Player").strip()[:80]

    if not sender_id or len(sender_id) > 120 or not command:
        record_usage(api_key, 400, endpoint)
        return jsonify(
            success=False,
            error="sender_id and command are required",
        ), 400

    try:
        player = get_player(sender_id, sender_name)
        reply = ""
        now = datetime.utcnow()

        if command in ("balance", "bal", "money"):
            reply = f"💰 {player.display_name}: {player.balance:,} ZENYN"

        elif command == "daily":
            if player.last_daily and now - player.last_daily < timedelta(hours=24):
                remaining = timedelta(hours=24) - (now - player.last_daily)
                reply = f"⏳ Daily reward already claimed. Try again in about {int(remaining.total_seconds() // 3600)}h."
            else:
                reward = random.randint(200, 500)
                player.balance += reward
                player.last_daily = now
                log_transaction(player, "daily", reward)
                reply = f"🎁 You received {reward:,} ZENYN! Balance: {player.balance:,}."

        elif command == "work":
            if player.last_work and now - player.last_work < timedelta(minutes=30):
                reply = "⏳ You're tired. Try working again in 30 minutes."
            else:
                reward = random.randint(50, 200)
                player.balance += reward
                player.last_work = now
                log_transaction(player, "work", reward)
                reply = f"🛠️ You earned {reward:,} ZENYN. Balance: {player.balance:,}."

        elif command == "heist":
            if player.last_heist and now - player.last_heist < timedelta(hours=2):
                reply = "🚨 Your next heist is available after the cooldown."
            else:
                player.last_heist = now
                if random.random() < 0.55:
                    reward = random.randint(250, 800)
                    player.balance += reward
                    log_transaction(player, "heist_win", reward)
                    reply = f"💎 Heist successful! +{reward:,} ZENYN."
                else:
                    loss = min(player.balance, random.randint(100, 300))
                    player.balance -= loss
                    log_transaction(player, "heist_loss", -loss)
                    reply = f"🚔 You got caught and lost {loss:,} ZENYN."

        elif command == "rob":
            if not target_id or target_id == sender_id:
                reply = "Usage: !rob @member"
            else:
                target = get_player(target_id, target_name)
                if target.balance <= 0:
                    reply = "That player has no ZENYN to rob."
                elif random.random() < 0.45:
                    amount = min(target.balance, random.randint(20, 150))
                    target.balance -= amount
                    player.balance += amount
                    log_transaction(player, "rob_win", amount, target)
                    log_transaction(target, "robbed", -amount, player)
                    reply = f"🦹 You stole {amount:,} ZENYN from {target.display_name}."
                else:
                    fine = min(player.balance, random.randint(10, 75))
                    player.balance -= fine
                    log_transaction(player, "rob_failed", -fine, target)
                    reply = f"🚨 Robbery failed. You paid a {fine:,} ZENYN fine."

        elif command == "pay":
            if not target_id or target_id == sender_id:
                reply = "Usage: !pay @member amount"
            else:
                try:
                    amount = int(data.get("amount", 0))
                except (TypeError, ValueError):
                    amount = 0

                if amount <= 0:
                    reply = "Enter a positive payment amount."
                elif player.balance < amount:
                    reply = "Insufficient ZENYN."
                else:
                    target = get_player(target_id, target_name)
                    player.balance -= amount
                    target.balance += amount
                    log_transaction(player, "payment_sent", -amount, target)
                    log_transaction(target, "payment_received", amount, player)
                    reply = f"💸 Sent {amount:,} ZENYN to {target.display_name}."

        elif command == "leaderboard":
            leaders = ZentraPlayer.query.order_by(
                ZentraPlayer.balance.desc()
            ).limit(10).all()
            lines = [
                f"{index}. {p.display_name}: {p.balance:,} ZENYN"
                for index, p in enumerate(leaders, start=1)
            ]
            reply = "🏆 ZENYN LEADERBOARD\n" + ("\n".join(lines) if lines else "No players yet.")

        elif command == "roast":
            if not target_id:
                reply = "Usage: !roast @member"
            else:
                roasts = [
                    "Your Wi-Fi has more stability than your decisions 😂",
                    "Even your shadow needs some distance 😭",
                    "You bring loading-screen energy to every situation 💀",
                    "Your confidence is premium; your results are on the free plan 😂",
                ]
                reply = f"🔥 {target_name}: {random.choice(roasts)}"

        elif command == "marry":
            if not target_id or target_id == sender_id:
                reply = "Usage: !marry @member"
            else:
                target = get_player(target_id, target_name)
                already_married = ZentraMarriage.query.filter(
                    ZentraMarriage.accepted.is_(True),
                    db.or_(
                        db.and_(
                            ZentraMarriage.proposer_id == player.id,
                            ZentraMarriage.target_id == player.id,
                        ),
                        db.or_(
                            db.and_(
                                ZentraMarriage.proposer_id == player.id,
                                ZentraMarriage.target_id == target.id,
                            ),
                            db.and_(
                                ZentraMarriage.proposer_id == target.id,
                                ZentraMarriage.target_id == player.id,
                            ),
                        ),
                    ),
                ).first()

                if already_married:
                    reply = "💍 One of you is already married."
                else:
                    pending = ZentraMarriage.query.filter_by(
                        proposer_id=player.id,
                        target_id=target.id,
                        accepted=False,
                    ).first()
                    if pending:
                        reply = f"💌 A proposal to {target.display_name} is already pending."
                    else:
                        db.session.add(ZentraMarriage(
                            proposer_id=player.id,
                            target_id=target.id,
                            accepted=False,
                        ))
                        reply = f"💍 {player.display_name} proposed to {target.display_name}! They can reply with !acceptmarry."

        elif command == "acceptmarry":
            proposal = ZentraMarriage.query.filter_by(
                target_id=player.id,
                accepted=False,
            ).order_by(ZentraMarriage.id.desc()).first()

            if proposal is None:
                reply = "You have no pending marriage proposal."
            else:
                proposer = db.session.get(ZentraPlayer, proposal.proposer_id)
                other_active = ZentraMarriage.query.filter(
                    ZentraMarriage.accepted.is_(True),
                    db.or_(
                        db.and_(
                            ZentraMarriage.proposer_id == player.id,
                            ZentraMarriage.target_id == player.id,
                        ),
                        db.or_(
                            db.and_(
                                ZentraMarriage.proposer_id == player.id,
                                ZentraMarriage.target_id == proposal.proposer_id,
                            ),
                            db.and_(
                                ZentraMarriage.proposer_id == proposal.proposer_id,
                                ZentraMarriage.target_id == player.id,
                            ),
                        ),
                    ),
                ).first()

                if other_active:
                    reply = "💍 One of you is already married."
                else:
                    proposal.accepted = True
                    reply = f"💞 {player.display_name} accepted {proposer.display_name}'s proposal!"

        else:
            record_usage(api_key, 400, endpoint)
            return jsonify(
                success=False,
                error="Unknown command",
                supported=[
                    "balance", "daily", "work", "rob", "heist",
                    "pay", "leaderboard", "roast", "marry", "acceptmarry",
                ],
            ), 400

        db.session.commit()
        api_key.last_used = now
        record_usage(api_key, 200, endpoint)

        return jsonify(
            success=True,
            command=command,
            reply=reply,
            player={
                "id": player.platform_id,
                "name": player.display_name,
                "balance": player.balance,
                "currency": "ZENYN",
            },
        ), 200

    except ValueError as exc:
        db.session.rollback()
        record_usage(api_key, 400, endpoint)
        return jsonify(success=False, error=str(exc)), 400
    except Exception:
        db.session.rollback()
        return jsonify(
            success=False,
            error="Internal server error",
        ), 500
