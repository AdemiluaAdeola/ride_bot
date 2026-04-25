"""
SlickRide Telegram Bot
Wires the assistant conversation logic to the FastAPI backend.
Uses python-telegram-bot v20+ (async).

Each user's ride state is tracked in-memory per chat_id.
For multi-process deployments, replace `user_sessions` with Redis.
"""

import os
import asyncio
import httpx
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
API_BASE  = os.getenv("SLICKRIDE_API_URL", "http://localhost:8000")

# ── Conversation states ───────────────────────────────────────────────────────
(
    ONBOARD_NAME,
    ONBOARD_EMAIL,
    ONBOARD_PHONE,
    IDLE,
    AWAITING_PICKUP,
    AWAITING_DESTINATION,
    AWAITING_CONFIRMATION,
    AWAITING_PAYMENT_REF,
    AWAITING_RIDE_CODE,
    AWAITING_FEEDBACK_RATING,
    AWAITING_FEEDBACK_COMMENT,
) = range(11)

# ── Helpers ───────────────────────────────────────────────────────────────────
async def api(method: str, path: str, **kwargs):
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
        r = await getattr(client, method)(path, **kwargs)
        r.raise_for_status()
        return r.json()


def kb(*rows):
    """Build a simple reply keyboard."""
    return ReplyKeyboardMarkup([[b for b in row] for row in rows],
                               resize_keyboard=True, one_time_keyboard=True)


def no_kb():
    return ReplyKeyboardRemove()


# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    tid = str(update.effective_user.id)
    try:
        user = await api("get", f"/users/by-telegram/{tid}")
        ctx.user_data["user"] = user
        await update.message.reply_text(
            f"Welcome back, {user['name']}! 👋\nReady to ride?",
            reply_markup=kb(["🚗 Book a ride"], ["📋 My rides"]),
        )
        return IDLE
    except httpx.HTTPStatusError:
        await update.message.reply_text(
            "👋 Welcome to *SlickRide!*\n\nLet's get you set up. What's your full name?",
            parse_mode="Markdown",
            reply_markup=no_kb(),
        )
        return ONBOARD_NAME


# ── Onboarding ────────────────────────────────────────────────────────────────
async def onboard_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["reg_name"] = update.message.text.strip()
    await update.message.reply_text("Got it! What's your email address?")
    return ONBOARD_EMAIL


async def onboard_email(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    if "@" not in email:
        await update.message.reply_text("That doesn't look like a valid email. Try again:")
        return ONBOARD_EMAIL
    ctx.user_data["reg_email"] = email
    await update.message.reply_text("And your phone number? (e.g. 08012345678)")
    return ONBOARD_PHONE


async def onboard_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    tid   = str(update.effective_user.id)
    try:
        user = await api("post", "/users/", json={
            "name":        ctx.user_data["reg_name"],
            "email":       ctx.user_data["reg_email"],
            "phone":       phone,
            "telegram_id": tid,
        })
        ctx.user_data["user"] = user
        await update.message.reply_text(
            f"You're all set, {user['name']}! 🎉\nTap below whenever you need a ride.",
            reply_markup=kb(["🚗 Book a ride"]),
        )
        return IDLE
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Registration failed.")
        await update.message.reply_text(f"⚠️ {detail}\nTry /start again.")
        return ConversationHandler.END


# ── Idle ──────────────────────────────────────────────────────────────────────
async def idle(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    if "book" in text or "ride" in text:
        await update.message.reply_text("Where are you right now? (Pickup location)",
                                        reply_markup=no_kb())
        return AWAITING_PICKUP
    if "my rides" in text:
        return await my_rides(update, ctx)
    await update.message.reply_text("Tap *Book a ride* to get started! 🚗",
                                    parse_mode="Markdown",
                                    reply_markup=kb(["🚗 Book a ride"]))
    return IDLE


async def my_rides(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    user = ctx.user_data.get("user")
    if not user:
        return IDLE
    try:
        rides = await api("get", f"/rides/user/{user['id']}")
        if not rides:
            await update.message.reply_text("You haven't taken any rides yet.",
                                            reply_markup=kb(["🚗 Book a ride"]))
            return IDLE
        lines = []
        for r in rides[:5]:
            lines.append(f"• {r['pickup']} → {r['destination']}  ₦{r['fare']:.0f}  [{r['status']}]")
        await update.message.reply_text("Your last rides:\n" + "\n".join(lines),
                                        reply_markup=kb(["🚗 Book a ride"]))
    except Exception:
        await update.message.reply_text("Couldn't fetch rides right now.",
                                        reply_markup=kb(["🚗 Book a ride"]))
    return IDLE


# ── Booking flow ──────────────────────────────────────────────────────────────
async def got_pickup(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["pickup"] = update.message.text.strip()
    await update.message.reply_text("Where are you headed? (Drop-off location)")
    return AWAITING_DESTINATION


async def got_destination(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    user    = ctx.user_data.get("user")
    pickup  = ctx.user_data["pickup"]
    dest    = update.message.text.strip()
    ctx.user_data["destination"] = dest

    await update.message.reply_text("Finding your fare... ⏳", reply_markup=no_kb())

    try:
        ride = await api("post", "/rides/", json={
            "user_id":     user["id"],
            "pickup":      pickup,
            "destination": dest,
        })
        ctx.user_data["ride"] = ride
        risk = ride["risk_level"]

        fare_msg = (
            f"📍 *{pickup}* → *{dest}*\n"
            f"💰 Fare: ₦{ride['fare']:.0f}\n"
            f"🚗 ETA: ~8 min"
        )

        if risk == "high":
            await update.message.reply_text(
                "We're unable to proceed with this request right now. "
                "Please try again later or contact support.",
                reply_markup=kb(["🚗 Book a ride"]),
            )
            return IDLE

        if risk == "medium":
            await update.message.reply_text(
                fare_msg + "\n\n⚠️ _Just to confirm_ — this is the ride you want?",
                parse_mode="Markdown",
                reply_markup=kb(["✅ Yes, confirm"], ["❌ Cancel"]),
            )
        else:
            await update.message.reply_text(
                fare_msg + "\n\nConfirm this ride?",
                parse_mode="Markdown",
                reply_markup=kb(["✅ Confirm"], ["❌ Cancel"]),
            )
        return AWAITING_CONFIRMATION

    except httpx.HTTPStatusError as e:
        await update.message.reply_text("Something went wrong. Retrying...")
        return IDLE


async def got_confirmation(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()

    if "cancel" in text:
        ride = ctx.user_data.get("ride")
        if ride:
            try:
                await api("delete", f"/rides/{ride['id']}/cancel")
            except Exception:
                pass
        await update.message.reply_text("Ride cancelled. No charge made. 👍",
                                        reply_markup=kb(["🚗 Book a ride"]))
        return IDLE

    if "confirm" in text or "yes" in text:
        ride = ctx.user_data.get("ride")
        try:
            await api("post", f"/rides/{ride['id']}/confirm")
            await update.message.reply_text(
                "Ride confirmed! 💳\n\nSend your *Paystack/Flutterwave payment reference* to complete booking:",
                parse_mode="Markdown",
                reply_markup=no_kb(),
            )
            return AWAITING_PAYMENT_REF
        except httpx.HTTPStatusError as e:
            detail = e.response.json().get("detail", "Could not confirm ride.")
            await update.message.reply_text(f"⚠️ {detail}")
            return IDLE

    await update.message.reply_text("Please tap Confirm or Cancel.",
                                    reply_markup=kb(["✅ Confirm"], ["❌ Cancel"]))
    return AWAITING_CONFIRMATION


async def got_payment_ref(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ref  = update.message.text.strip()
    ride = ctx.user_data.get("ride")

    await update.message.reply_text("We're confirming your payment... ⏳")

    try:
        await api("post", "/payments/verify", json={
            "ride_id":   ride["id"],
            "reference": ref,
        })
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Payment verification failed.")
        await update.message.reply_text(f"⚠️ {detail}\nPlease try again or contact support.")
        return AWAITING_PAYMENT_REF

    await update.message.reply_text("Payment confirmed ✅\nAssigning your driver...")

    try:
        updated_ride = await api("post", f"/rides/{ride['id']}/assign-driver")
        ctx.user_data["ride"] = updated_ride
        await update.message.reply_text(
            f"🚗 Driver assigned!\n\n"
            f"Your *ride code* is:\n\n`{updated_ride['ride_code']}`\n\n"
            f"Show this to your driver to start the trip.",
            parse_mode="Markdown",
            reply_markup=kb(["▶️ Start ride (enter code)"]),
        )
        return AWAITING_RIDE_CODE
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Driver assignment failed.")
        await update.message.reply_text(f"⚠️ {detail}")
        return IDLE


async def got_ride_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    ride = ctx.user_data.get("ride")

    # If user tapped the button instead of typing the code
    if "start ride" in text.lower():
        await update.message.reply_text("Enter the 4-digit code your driver shows you:",
                                        reply_markup=no_kb())
        return AWAITING_RIDE_CODE

    try:
        await api("post", f"/rides/{ride['id']}/start", json={"ride_code": text})
        await update.message.reply_text(
            "🟢 Ride started! Enjoy the trip.\n\nTap *End ride* when you arrive.",
            parse_mode="Markdown",
            reply_markup=kb(["🔴 End ride"]),
        )
        return IDLE  # reuse IDLE, end-ride handled as special message
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Invalid code.")
        await update.message.reply_text(f"❌ {detail}")
        return AWAITING_RIDE_CODE


# ── End ride (handled from IDLE) ──────────────────────────────────────────────
async def end_ride_from_idle(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ride = ctx.user_data.get("ride")
    if not ride:
        return await idle(update, ctx)

    try:
        updated = await api("post", f"/rides/{ride['id']}/end")
        ctx.user_data["ride"] = updated
        await update.message.reply_text(
            f"🎉 You've arrived! Total: ₦{updated['fare']:.0f}\n\n"
            "How was your ride? Rate 1–5:",
            reply_markup=kb(["⭐ 1"], ["⭐⭐ 2"], ["⭐⭐⭐ 3"], ["⭐⭐⭐⭐ 4"], ["⭐⭐⭐⭐⭐ 5"]),
        )
        return AWAITING_FEEDBACK_RATING
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Could not end ride.")
        await update.message.reply_text(f"⚠️ {detail}")
        return IDLE


# ── Feedback ──────────────────────────────────────────────────────────────────
async def got_rating(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    rating = text.count("⭐") or (int(text) if text.isdigit() else None)
    if not rating or not (1 <= rating <= 5):
        await update.message.reply_text("Please pick a rating from 1 to 5.")
        return AWAITING_FEEDBACK_RATING
    ctx.user_data["rating"] = rating
    await update.message.reply_text(
        "Any comments? (or tap Skip)",
        reply_markup=kb(["Skip"]),
    )
    return AWAITING_FEEDBACK_COMMENT


async def got_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text    = update.message.text.strip()
    comment = None if text.lower() == "skip" else text
    ride    = ctx.user_data.get("ride")
    rating  = ctx.user_data.get("rating", 5)

    try:
        await api("post", "/feedback/", json={
            "ride_id": ride["id"],
            "rating":  rating,
            "comment": comment,
        })
    except Exception:
        pass  # feedback failure shouldn't block the user

    stars = "⭐" * rating
    await update.message.reply_text(
        f"{stars} — thanks for the feedback!\n\nNeed another ride?",
        reply_markup=kb(["🚗 Book a ride"]),
    )
    ctx.user_data.pop("ride", None)
    return IDLE


# ── Cancel command ────────────────────────────────────────────────────────────
async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled. Type /start to begin again.",
                                    reply_markup=no_kb())
    return ConversationHandler.END


# ── Error handler ─────────────────────────────────────────────────────────────
async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    print(f"[ERROR] {ctx.error}")
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("Something went wrong. Retrying... or type /start.")


# ── App entry ─────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ONBOARD_NAME:             [MessageHandler(filters.TEXT & ~filters.COMMAND, onboard_name)],
            ONBOARD_EMAIL:            [MessageHandler(filters.TEXT & ~filters.COMMAND, onboard_email)],
            ONBOARD_PHONE:            [MessageHandler(filters.TEXT & ~filters.COMMAND, onboard_phone)],
            IDLE:                     [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c:
                                        end_ride_from_idle(u, c) if "end ride" in u.message.text.lower()
                                        else idle(u, c))],
            AWAITING_PICKUP:          [MessageHandler(filters.TEXT & ~filters.COMMAND, got_pickup)],
            AWAITING_DESTINATION:     [MessageHandler(filters.TEXT & ~filters.COMMAND, got_destination)],
            AWAITING_CONFIRMATION:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_confirmation)],
            AWAITING_PAYMENT_REF:     [MessageHandler(filters.TEXT & ~filters.COMMAND, got_payment_ref)],
            AWAITING_RIDE_CODE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, got_ride_code)],
            AWAITING_FEEDBACK_RATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_rating)],
            AWAITING_FEEDBACK_COMMENT:[MessageHandler(filters.TEXT & ~filters.COMMAND, got_comment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_chat=True,
    )

    app.add_handler(conv)
    app.add_error_handler(error_handler)

    print("SlickRide Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
