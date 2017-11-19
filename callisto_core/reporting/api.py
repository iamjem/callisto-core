import logging

from callisto_core.utils.api import NotificationApi

logger = logging.getLogger(__name__)


class CallistoCoreMatchingApi(object):

    def find_matches(self, match_reports_to_check, to_addresses):
        """Finds sets of matching records that haven't been identified yet. For a match to count as new, there must be
        associated Reports from at least 2 different users and at least one MatchReport must be newly created since
        we last checked for matches.

        Args:
          match_reports_to_check (list of MatchReports): the MatchReports to check for matches
        """
        from callisto_core.delivery.models import MatchReport
        for match_report in match_reports_to_check:
            identifier = match_report.identifier
            match_list = [
                potential_match_report
                for potential_match_report in MatchReport.objects.all()
                if potential_match_report.get_match(identifier)
            ]
            if len(match_list) > 1:
                seen_match_owners = [
                    match.report.owner for match in match_list
                    if match.seen
                ]
                new_match_owners = [
                    match.report.owner for match in match_list
                    if not match.seen
                ]
                # filter out multiple reports made by the same person
                if len(set(seen_match_owners + new_match_owners)) > 1:
                    # only send notifications if new matches are submitted by
                    # owners we don't know about
                    if not set(new_match_owners).issubset(
                            set(seen_match_owners)):
                        self._process_new_matches(
                            match_list, identifier, to_addresses)
                    for matched_report in match_list:
                        matched_report.report.match_found = True
                        matched_report.report.save()
            for match in match_list:
                match.seen = True
                # delete identifier, which should only be filled for newly
                # added match reports in delayed matching case
                match.identifier = None
                match.save()

    def _process_new_matches(self, matches, identifier, to_addresses):
        """Sends a report to the receiving authority and notifies the reporting users.
        Each user should only be notified one time when a match is found.

        Args:
          matches (list of MatchReports): the MatchReports that correspond to this identifier
          identifier (str): identifier associated with the MatchReports
        """
        logger.info("new match found")
        owners_notified = []
        for match_report in matches:
            owner = match_report.report.owner
            # dont notify report owners twice for a single match
            if owner not in owners_notified:
                NotificationApi.send_match_notification(owner, match_report)
                owners_notified.append(owner)
        # send report to school
        NotificationApi.send_matching_report_to_authority(
            matches, identifier, to_addresses)
