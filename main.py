from enum import Enum
from typing import Dict, List, Optional, Tuple
from time import sleep
import plotly.graph_objects as go
import pickle

from datetime import datetime, timedelta
from github import Github
from github.GithubException import RateLimitExceededException
from github.Issue import Issue
from github.Label import Label
from github.IssueEvent import IssueEvent
from github.Repository import Repository

from progress.bar import Bar

# TODO:
# - Paste in Spec Core Team focus and have links generated for each MSC
#   entry automatically

TEXT = """
# Spec

Here's your weekly spec update! The heart of Matrix is the specification - and this is modified by Matrix Spec Change (MSC) proposals. Learn more about how the process works at https://matrix.org/docs/spec/proposals.


## MSC Status

**Merged MSCs:**
{merged_mscs}

**MSCs in Final Comment Period:**
{mscs_in_fcp}

**New MSCs:**
{new_mscs}

## Spec Core Team

In terms of Spec Core Team MSC focus for this week,
"""


class MSCState(Enum):
    NEW = 1
    FCP = 2
    MERGED = 3
    POSTPONED = 4
    CLOSED = 5


def main():
    # First create a Github instance
    # Just needs read:public_repo I think
    g = Github("")
    r = g.get_repo("matrix-org/matrix-doc")

    one_week_ago = datetime.now() - timedelta(days=7)

    # Get MSC Issues
    new_mscs = r.get_issues(
        state="open",
        labels=["proposal"],
        since=one_week_ago,
    )
    mscs_in_fcp = r.get_issues(
        state="open",
        labels=["proposal", "final-comment-period"],
    )
    closed_mscs = list(r.get_issues(
        state="closed",
        labels=["proposal", "rejected"],
    ))
    postponed_mscs = list(r.get_issues(
        state="open",
        labels=["proposal", "finished-final-comment-period", "disposition-postpone"],
    ))
    merged_mscs = [msc for msc in r.get_issues(
        state="closed",
        labels=["proposal"],
        since=one_week_ago,
    ) if msc not in closed_mscs and msc not in postponed_mscs]

    # The since= parameter above allows MSCs in that were commented on less than
    # one week ago, so we do some further filtering here.
    # This has the advantage of converting the PaginatedLists we get from the
    # Github module into normal ol' Lists
    new_mscs = [msc for msc in new_mscs if msc.created_at > one_week_ago]
    mscs_in_fcp = [msc for msc in mscs_in_fcp]
    merged_mscs = [msc for msc in merged_mscs if msc.closed_at > one_week_ago]

    # Convert MSC lists into text for the update
    if new_mscs:
        text = ""
        for msc in new_mscs:
            text += f"* [{msc.title}]({msc.html_url})\n"
        new_mscs = text.strip()
    else:
        new_mscs = "* *There were no new MSCs this week.*"

    if mscs_in_fcp:
        text = ""
        for msc in mscs_in_fcp:
            # Figure out disposition
            disposition = get_disposition(msc)
            text += f"* [{msc.title}]({msc.html_url}) ({disposition})\n"
        mscs_in_fcp = text.strip()
    else:
        mscs_in_fcp = "* *No MSCs are in FCP.*"

    if merged_mscs:
        text = ""
        for msc in merged_mscs:
            text += f"* [{msc.title}]({msc.html_url})\n"
        merged_mscs = text.strip()
    else:
        merged_mscs = "* *No MSCs were merged this week.*"

    # Replace placeholders in template
    update_text = TEXT.format(
        new_mscs=new_mscs,
        mscs_in_fcp=mscs_in_fcp,
        merged_mscs=merged_mscs,
    )
    print(update_text)

    # Generate a pie chart of MSC progress
    #generate_msc_pie_chart(r)

    # Generate a stacked area chart with historical MSC progress
    generate_stacked_area_chart(r)

def get_disposition(msc: Issue) -> str:
    """Returns the textual representation of the disposition of a MSC"""
    dispositions = ["merge", "close", "postpone"]
    for label in msc.get_labels():
        for disposition in dispositions:
            # label.name is something like 'disposition:merge'
            # disposition is something like 'merge'
            if disposition in label.name:
                return disposition

def generate_msc_pie_chart(r: Repository):
    # Get total number of {closed, open, merged, postponed, fcp} MSCs
    fcp_mscs = r.get_issues(
        state="open",
        labels=["proposal", "final-comment-period"],
    ).totalCount
    open_mscs = r.get_issues(state="open", labels=["proposal"]).totalCount - fcp_mscs
    closed_mscs = r.get_issues(
        state="closed",
        labels=["proposal", "rejected"],
    ).totalCount
    postponed_mscs = r.get_issues(
        state="open",
        labels=["proposal", "finished-final-comment-period", "disposition-postpone"],
    ).totalCount
    merged_mscs = r.get_issues(
        state="closed",
        labels=["proposal"],
    ).totalCount - closed_mscs - postponed_mscs

    # Create the pie chart
    labels = ["Open", "Merged", "Closed", "FCP", "Postponed"]
    colors = ["#28a745", "#6f42c1", "#ce303d", "yellow", "grey"]
    values = [open_mscs, merged_mscs, closed_mscs, fcp_mscs, postponed_mscs]

    # Add the respective count to each label
    for idx, label in enumerate(labels):
        labels[idx] = f"{label} ({values[idx]})"

    fig = go.Figure(
        data=[go.Pie(
            labels=labels,
            values=values,
            sort=False,  # Use order of lists above instead of sorting by size
        )],
    )
    # Make a nice title
    fig.update_layout(
        title={
            'text': "Matrix Spec Change Proposals",
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
        },
        font=dict(
            family="Arial",
            size=18,
            color="#222222",
        ),
    )
    fig.update_traces(hoverinfo="label+percent", textinfo="value", textfont_size=20,
                      marker=dict(colors=colors, line=dict(color="#000000", width=2)))
    fig.write_image("plot.png")


def generate_stacked_area_chart(r: Repository):
    """Generates a historical stacked area chart of msc status"""
    print("Generating stacked area chart. This will take some time.")

    # Get time of the earliest issue
    mscs = list(r.get_issues(
        sort="created",
        state="all",
        direction="asc",
        labels=["proposal"],
    ))

    # There are some MSCs that date all the way back to 2014. These skew the chart a bit,
    # so lop those off
    outlier_threshold = datetime.fromisoformat("2018-04-29T00:00:00")

    # Generate list of weeks since the first msc
    weeks = []
    t = mscs[0].created_at

    while t < datetime.now():
        if t > outlier_threshold:
            # Add t to our list of weeks
            weeks.append(t)

        # Move forward by three weeks
        t = t + timedelta(weeks=1)

    # And calculate it for today
    weeks.append(datetime.now())

    # Extract MSC event data beforehand so we don't do so again every week
    msc_events = []

    # Used for quick, iterative development purposes
    # Aka the loop below takes 25 min to run
    # with open('msc_events.pickle', 'rb') as handle:
    #     msc_events = pickle.load(handle)

    bar = Bar("Grabbing list of events for each MSC...", max=len(mscs))
    for msc in mscs:
        # TODO: We could theoretically optimize this by saving a list of events per
        # MSC in a DB between runs. If the count of events for a given MSC number
        # hasn't changed, then don't update the events
        # This would prevent us from needing to fetch the label for each event

        # Also try the GraphQL API

        # Loop until we succeeded in getting the events for this MSC
        while True:
            try:
                # Pre-request the event labels. This apparently takes another API call
                event_label_tuples = []
                for event in msc.get_events():
                    event_label_tuples.append(
                        (event, event.label if event.event == "labeled" else None)
                    )

                # Events retrieved, break out of the inner loop
                msc_events.append(event_label_tuples)
                break
            except RateLimitExceededException as e:
                # Wait a bit and retry
                print("\nHit Ratelimit. Waiting 1 minute...")
                sleep(60)

        bar.next()
    bar.finish()

    print("Got", sum([len(events) for events in msc_events]), "total events")

    # with open('msc_events.pickle', 'wb') as handle:
    #     pickle.dump(msc_events, handle, protocol=pickle.HIGHEST_PROTOCOL)

    # Get the count of each MSC type at a given week
    new_mscs = []
    fcp_mscs = []
    closed_mscs = []
    merged_mscs = []

    bar = Bar("Processing MSC state snapshots...", max=len(weeks))
    for week in weeks:
        new_msc_count = 0
        fcp_msc_count = 0
        closed_msc_count = 0
        merged_msc_count = 0
        for index, msc in enumerate(mscs):
            msc_state = get_msc_state_at_time(msc, msc_events[index], week)

            if msc_state == MSCState.NEW:
                new_msc_count += 1
            elif msc_state == MSCState.FCP:
                fcp_msc_count += 1
            elif msc_state == MSCState.CLOSED:
                closed_msc_count += 1
            elif msc_state == MSCState.MERGED:
                merged_msc_count += 1

        # Note down all counts for this week
        new_mscs.append(new_msc_count)
        fcp_mscs.append(fcp_msc_count)
        closed_mscs.append(closed_msc_count)
        merged_mscs.append(merged_msc_count)

        bar.next()
    bar.finish()

    str_weeks = [dt.strftime("%d-%m-%Y") for dt in weeks]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=str_weeks, y=new_mscs,
        hoverinfo='x+y',
        mode='lines',
        name='New',
        line=dict(width=0.5, color='#28a745'),
        stackgroup='one'
    ))
    fig.add_trace(go.Scatter(
        x=str_weeks, y=fcp_mscs,
        hoverinfo='x+y',
        mode='lines',
        name='FCP',
        line=dict(width=0.5, color='yellow'),
        stackgroup='one'
    ))
    fig.add_trace(go.Scatter(
        x=str_weeks, y=closed_mscs,
        hoverinfo='x+y',
        mode='lines',
        name='Closed',
        line=dict(width=0.5, color='#ce303d'),
        stackgroup='one'
    ))
    fig.add_trace(go.Scatter(
        x=str_weeks, y=merged_mscs,
        hoverinfo='x+y',
        mode='lines',
        name='Merged',
        line=dict(width=0.5, color='#6f42c1'),
        stackgroup='one'
    ))

    # Add a nice title
    fig.update_layout(
        title={
            'text': "Matrix Spec Change Proposals",
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
        },
        font=dict(
            family="Arial",
            size=18,
            color="#222222",
        ),
    )
    fig.write_image("stacked_area_chart.png")


def get_msc_state_at_time(
    msc: Issue,
    msc_events: List[Tuple[IssueEvent, Optional[Label]]],
    dt: datetime,
) -> MSCState:
    # Iterate through MSC events and calculate the current state of the issue at a given
    # time
    # Initially assume it doesn't exist. Change the state as we iterate through events
    state = {"prev_state": None, "state": None}  # type: Dict[str, Optional[MSCState]]
    finished_fcp = False

    def update_state(new_state: MSCState):
        state["prev_state"] = state["state"]
        state["state"] = new_state

    disposition_state = None
    is_closed = False
    has_label_merged = False
    rejected_or_abandoned = False
    for event, label in msc_events:
        if event.created_at > dt:
            # We've reached our datetime threshold
            break

        # Classify the event
        if label:
            label_name = label.name

            # This is a label event
            if label_name == "proposal":
                update_state(MSCState.NEW)
            elif label_name == "final-comment-period":
                update_state(MSCState.FCP)
            elif label_name == "disposition-merge":
                disposition_state = MSCState.MERGED
            elif label_name == "disposition-close":
                disposition_state = MSCState.CLOSED
            elif label_name == "disposition-postpone":
                disposition_state = MSCState.POSTPONED
            # Some issues have this silly label
            # i.e https://github.com/matrix-org/matrix-doc/issues/1466
            elif label_name == "merged":
                update_state(MSCState.MERGED)
                has_label_merged = True
            elif label_name == "finished-final-comment-period":
                # Prevent issues which have finished FCP but associated PRs have not
                # merged yet to not get stuck in FCP state forever.
                # i.e https://github.com/matrix-org/matrix-doc/issues/1219
                update_state(disposition_state if disposition_state else MSCState.NEW)
                finished_fcp = True
            elif label_name == "abandoned" or label_name == "rejected":
                update_state(MSCState.CLOSED)
        elif event.event == "reopened":
            # TODO: What does mscbot-python do in this case? New or previous state?
            update_state(state["prev_state"])
            is_closed = False
        elif event.event == "closed":
            # The MSC was closed
            if msc.pull_request:
                if state != MSCState.MERGED:
                    update_state(MSCState.CLOSED)
            # Issues that are closed count as closed MSCs
            else:
                if has_label_merged:
                    update_state(MSCState.MERGED)
                else:
                    update_state(MSCState.CLOSED)
        elif event.event == "merged":
            # The MSC was merged
            if finished_fcp:
                update_state(MSCState.MERGED)

        if is_closed and rejected_or_abandoned:
            update_state(MSCState.CLOSED)

    return state["state"]

if __name__ == '__main__':
    main()