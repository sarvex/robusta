import logging
from datetime import datetime
from typing import List, Optional

try:
    from grafana_api.grafana_face import GrafanaFace  # type: ignore
except ImportError:

    def GrafanaFace(*args, **kwargs):
        raise ImportError("grafana-api is not installed")


from robusta.core.model.env_vars import GRAFANA_READ_TIMEOUT
from robusta.utils.service_discovery import find_service_url


class Grafana:
    def __init__(self, api_key, grafana_url=None):
        """
        Create a new connection to Grafana.

        :param grafana_url: if None, then attempt to discover the address of an in-cluster Grafana service
        """
        if grafana_url is None:
            grafana_url = find_service_url("app.kubernetes.io/name=grafana")
            assert grafana_url is not None, "Could not find Grafana service"

        protocol_host = grafana_url.split("://")
        logging.debug(f"Grafana params: protocol - {protocol_host[0]} host - {protocol_host[1]}")
        self.grafana = GrafanaFace(
            auth=api_key,
            protocol=protocol_host[0],
            host=protocol_host[1],
            timeout=GRAFANA_READ_TIMEOUT,
        )

    def add_line_to_dashboard(
        self,
        dashboard_uid: str,
        text: str,
        time: Optional[datetime] = None,
        tags: List[str] = [],
        panel_substring: Optional[str] = None,
    ):
        if time is None:
            time = datetime.now()
        self.__add_annotation(
            dashboard_uid,
            text,
            start_time=time,
            tags=tags,
            panel_substring=panel_substring,
        )

    def add_range_to_dashboard(
        self,
        dashboard_uid: str,
        text: str,
        start_time: datetime,
        end_time: datetime,
        tags: List[str] = [],
        panel_substring: Optional[str] = None,
    ):
        self.__add_annotation(
            dashboard_uid,
            text,
            start_time=start_time,
            end_time=end_time,
            tags=tags,
            panel_substring=panel_substring,
        )

    def __add_annotation(
        self,
        dashboard_uid: str,
        text: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        tags: List[str] = [],
        panel_substring: Optional[str] = None,
    ):
        dashboard = self.grafana.dashboard.get_dashboard(dashboard_uid)["dashboard"]
        dashboard_id = dashboard["id"]

        # grafana wants the timestamp as an int with millisecond resolution
        start_time_ = int(start_time.timestamp()) * 1000
        end_time_ = int(end_time.timestamp()) * 1000 if end_time is not None else None

        # add an annotation for the entire dashboard
        if panel_substring is None:
            resp = self.grafana.annotations.add_annotation(
                dashboard_id=dashboard_id,
                text=text,
                tags=tags,
                time_from=start_time_,
                time_to=end_time_,
            )
            logging.debug(f"grafana dashboard annotation response {resp}")
        # add an annotation to specific panels only
        else:
            panel_ids = self.__get_panels_with_substring(dashboard, panel_substring)
            for panel_id in panel_ids:
                resp = self.grafana.annotations.add_annotation(
                    dashboard_id=dashboard_id,
                    panel_id=panel_id,
                    text=text,
                    tags=tags,
                    time_from=start_time_,
                    time_to=end_time_,
                )
                logging.debug(f"grafana panel annotation response {resp}")

    def __get_panels_with_substring(self, dashboard, panel_substring):
        panel_ids = []
        for row in dashboard["rows"]:
            for panel in row["panels"]:
                if panel_substring.lower() in panel["title"].lower():
                    panel_ids.append(panel["id"])
        return panel_ids
