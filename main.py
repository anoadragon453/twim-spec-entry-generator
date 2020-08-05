from datetime import datetime, timedelta
from github import Github
from github.Issue import Issue
from msc_chart_generator.msc_chart import MSCChart, ChartType

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


def main():
    github_token = ""
    g = Github(github_token)
    r = g.get_repo("matrix-org/matrix-doc")
    msc_chart = MSCChart(pygithub=g)

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

    # Generate a chart of MSC progress
    msc_chart.generate(ChartType.STACKED_AREA, "stacked_area_chart.png")


def get_disposition(msc: Issue) -> str:
    """Returns the textual representation of the disposition of a MSC"""
    dispositions = ["merge", "close", "postpone"]
    for label in msc.get_labels():
        for disposition in dispositions:
            # label.name is something like 'disposition:merge'
            # disposition is something like 'merge'
            if disposition in label.name:
                return disposition

if __name__ == '__main__':
    main()
