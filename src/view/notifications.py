from dto import SpeechDto


def render_starting(speech: SpeechDto, time_to_start: int):
    return f'Через {time_to_start} минут начинается доклад "{speech.title}" ({speech.location})'


def render_settings(enabled: bool):
    return f'Текущие настройки:\nУведомления {"включены" if enabled else "выключены"}'
