from max_bot.keyboards.app_keyboard import get_app_keyboard
from maxapi import Router


router = Router()


@router.message_created()
async def start_handler(event):

    if event.message.body.text == "/start":
        print("Start написали")
        keyboard = get_app_keyboard(
            event.bot.me.user_id
        )

        print(keyboard.pack())

        await event.bot.send_message(
            chat_id=event.message.recipient.chat_id,
            text="Добро пожаловать в MAX Study",
            attachments=[
                keyboard.pack()
            ]
        )