from maxapi import F, Router
from maxapi.types import MessageCreated

router = Router()


@router.message_created(F.message.body.text)
async def text_handler(event: MessageCreated):
    await event.message.answer(f"Получил: {event.message.body.text}")
