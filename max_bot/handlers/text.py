from maxapi import Router


router = Router()


@router.message_created()
async def text_handler(event):

    text = event.message.body.text

    await event.bot.send_message(
        chat_id=event.message.recipient.chat_id,
        text=f"Получил: {text}"
    )