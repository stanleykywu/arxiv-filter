import os
from datetime import datetime
from pytz import timezone
import logging

import arxiv
from dotenv import load_dotenv

from utils.mailtrap_utils import send_message

load_dotenv()
RECENT_DAYS = 8


class Query(object):
    def __init__(self, query):
        self.date = datetime(*query["published_parsed"][:6], tzinfo=timezone("GMT"))
        self.url = query["link"]
        self.title = query["title"]
        self.authors = ", ".join([q["name"] for q in query["authors"]])
        self.abstract = query["summary"]
        self.date_str = query["published"]
        self.id = "v".join(query["id"].split("v")[:-1])
        self.categories = [tag["term"] for tag in query["tags"]]

    @property
    def is_recent(self):
        curr_time = datetime.now(timezone("GMT"))
        delta_time = curr_time - self.date
        assert delta_time.total_seconds() > 0
        return delta_time.days < RECENT_DAYS

    def __hash__(self):
        return self.id

    def __str__(self):
        s = ""
        s += self.title + "\n"
        s += self.url + "\n"
        s += self.authors + "\n"
        s += ", ".join(self.categories) + "\n"
        s += self.date.ctime() + " GMT \n"
        s += "\n" + self.abstract + "\n"
        # return s.encode("utf-8")
        return s


class ArxivFilter(object):
    def __init__(self, categories, keywords, email_address):
        self._arxiv_client = arxiv.Client()
        self._categories = categories
        self._keywords = keywords
        self._email_address = email_address
        self._sender_address = "dad@thedailyarxivdigest.ai"

    @property
    def _previous_arxivs_fname(self):
        return os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "previous_arxivs.txt"
        )

    def _get_previously_sent_arxivs(self):
        if os.path.exists(self._previous_arxivs_fname):
            with open(self._previous_arxivs_fname, "r") as f:
                return set(f.read().split("\n"))
        else:
            return set()

    def _save_previously_sent_arxivs(self, new_queries):
        prev_arxivs = list(self._get_previously_sent_arxivs())
        prev_arxivs += [q.id for q in new_queries]
        prev_arxivs = list(set(prev_arxivs))
        with open(self._previous_arxivs_fname, "w") as f:
            f.write("\n".join(prev_arxivs))

    def _get_queries_from_last_day(self):
        queries = []

        # get all queries in the categories in the last day
        for category in self._categories:
            logging.info(f"Searching for {category}...")
            category_results = []
            while True:
                for search_result in self._arxiv_client.results(
                    arxiv.Search(
                        query=category,
                        sort_by=arxiv.SortCriterion.SubmittedDate,
                    )
                ):
                    query = Query(search_result._raw)
                    if query.is_recent:
                        category_results.append(query)
                    else:
                        break

                break

            queries += category_results

        # get rid of duplicates
        queries_dict = {q.id: q for q in queries}
        unique_keys = set(queries_dict.keys())
        queries = [queries_dict[k] for k in unique_keys]

        # only keep queries that contain keywords
        queries = [
            q
            for q in queries
            if any([k.lower() in str(q).lower() for k in self._keywords])
        ]

        # sort from most recent to least
        queries = sorted(
            queries,
            key=lambda q: (datetime.now(timezone("GMT")) - q.date).total_seconds(),
        )

        # filter if previously sent
        prev_arxivs = self._get_previously_sent_arxivs()
        queries = [q for q in queries if q.id not in prev_arxivs]
        self._save_previously_sent_arxivs(queries)

        return queries

    def run(self):
        queries = self._get_queries_from_last_day()
        now = datetime.now()
        date_str = str(now.date())
        msg = ["<h1>arXiv results for {}</h1>".format(date_str)]

        for entry in queries:
            msg.append("<h2>{}</h2>".format(entry.title))
            msg.append("<h3>{}</h3>".format(entry.authors))
            msg.append("<p>{}</p>".format(entry.abstract))
            num = "arXiv:" + entry.id.split("/")[-1]
            link = '<a href="{}">{}</a>'.format(entry.id, num)
            pdf_link = '[<a href="{}">pdf</a>]'.format(entry.id.replace("abs", "pdf"))
            msg.append(link + " " + pdf_link)

        keywords = ", ".join(self._keywords)
        footer = "<p><em>Selected keywords: {}</em></p>"
        msg.append(footer.format(keywords))

        if not msg:
            msg = "<p>Luck you, no new readings today...</p>"
        else:
            msg = "".join(msg)

        send_message(
            message_content=msg,
            to_address=self._email_address,
            api_key=os.environ["MAILTRAP_API_TOKEN"],
        )


FILE_DIR = os.path.dirname(os.path.realpath(__file__))

with open(os.path.join(FILE_DIR, "categories.txt"), "r") as f:
    categories = [
        line.strip() for line in f.read().split("\n") if len(line.strip()) > 0
    ]

with open(os.path.join(FILE_DIR, "keywords.txt"), "r") as f:
    keywords = [line.strip() for line in f.read().split("\n") if len(line.strip()) > 0]

with open(os.path.join(FILE_DIR, "email_address.txt"), "r") as f:
    email_address = f.read().strip()

af = ArxivFilter(
    categories=categories,
    keywords=keywords,
    email_address=email_address,
)
af.run()
