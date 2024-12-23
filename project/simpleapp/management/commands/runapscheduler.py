import logging

from django.conf import settings

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django.core.mail import send_mail

from simpleapp.models import Category, Post
from django.utils import timezone
from datetime import timedelta
from django.utils.html import format_html

logger = logging.getLogger(__name__)


# наша задача по выводу текста на экран
def my_job():
    today = timezone.now()
    week_ago = today - timedelta(weeks=1)  # Считаем дату 7 дней назад

    categories = Category.objects.all()  # Получаем все категории

    # Словарь для накопления новостей по категориям
    category_news = {}

    for category in categories:
        # Получаем новые статьи за последнюю неделю в данной категории
        new_posts = category.post_set.filter(post_time__gte=week_ago)

        if new_posts:
            # Формируем список ссылок с заголовками для категории

            posts = [
                f'<a href="http://127.0.0.1:8000{post.get_absolute_url()}">'
                f'{" ".join(post.title.split()) if len(post.title.split()) <= 5 else " ".join(post.title.split()[:5]) + "..."}</a>'
                for post in new_posts
            ]
            category_news[category.name] = posts

    # Если есть новости для отправки, формируем письмо
    if category_news:
        email_body = ""

        for category, posts in category_news.items():
            email_body += f"<h3>Вот новости из категории {category}:</h3><ul>"
            email_body += "".join(f"<li>{post}</li>" for post in posts)
            email_body += "</ul><br>"

        # Получаем всех подписчиков, исключая дубликаты
        subscribers = set(
            subscriber.email
            for category in categories
            for subscriber in category.subscribers.all()
        )

        # Отправляем письмо всем подписчикам
        send_mail(
            'Новости за неделю!',
            '',  # Пустое текстовое содержимое
            from_email='Shapch1c@yandex.ru',
            recipient_list=list(subscribers),
            html_message=email_body  # Формат HTML для отображения ссылок
        )



# функция, которая будет удалять неактуальные задачи
def delete_old_job_executions(max_age=604_800):
    """This job deletes all apscheduler job executions older than `max_age` from the database."""
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class Command(BaseCommand):
    help = "Runs apscheduler."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # добавляем работу нашему задачнику
        scheduler.add_job(
            my_job,
            # trigger=CronTrigger(second="*/10"), # проверка работоспособности
            trigger=CronTrigger(day_of_week="sun", hour="23", minute="59"),
            # То же, что и интервал, но задача тригера таким образом более понятна django
            id="my_job",  # уникальный айди
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'my_job'.")

        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(
                day_of_week="mon", hour="00", minute="00"
            ),
            # Каждую неделю будут удаляться старые задачи, которые либо не удалось выполнить, либо уже выполнять не надо.
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        logger.info(
            "Added weekly job: 'delete_old_job_executions'."
        )

        try:
            logger.info("Starting scheduler...")
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Stopping scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler shut down successfully!")