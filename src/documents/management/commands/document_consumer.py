import datetime
import logging
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...consumer import Consumer, ConsumerError
from ...mail import MailFetcher, MailFetcherError


class Command(BaseCommand):
    """
    On every iteration of an infinite loop, consume what we can from the
    consumption directory, and fetch any mail available.
    """

    LOOP_TIME = settings.CONSUMER_LOOP_TIME
    MAIL_DELTA = datetime.timedelta(minutes=10)

    ORIGINAL_DOCS = os.path.join(settings.MEDIA_ROOT, "documents", "originals")
    THUMB_DOCS = os.path.join(settings.MEDIA_ROOT, "documents", "thumbnails")

    def __init__(self, *args, **kwargs):

        self.verbosity = 0

        self.file_consumer = None
        self.mail_fetcher = None
        self.first_iteration = True

        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]

        try:
            self.file_consumer = Consumer()
            self.mail_fetcher = MailFetcher()
        except (ConsumerError, MailFetcherError) as e:
            raise CommandError(e)

        for path in (self.ORIGINAL_DOCS, self.THUMB_DOCS):
            try:
                os.makedirs(path)
            except FileExistsError:
                pass

        logging.getLogger(__name__).info(
            "Starting document consumer at {}".format(settings.CONSUMPTION_DIR)
        )

        try:
            while True:
                self.loop()
                time.sleep(self.LOOP_TIME)
                if self.verbosity > 1:
                    print(".")
        except KeyboardInterrupt:
            print("Exiting")

    def loop(self):

        # Consume whatever files we can
        self.file_consumer.consume()

        # Occasionally fetch mail and store it to be consumed on the next loop
        # We fetch email when we first start up so that it is not necessary to
        # wait for 10 minutes after making changes to the config file.
        delta = self.mail_fetcher.last_checked + self.MAIL_DELTA
        if self.first_iteration or delta < datetime.datetime.now():
            self.first_iteration = False
            self.mail_fetcher.pull()
