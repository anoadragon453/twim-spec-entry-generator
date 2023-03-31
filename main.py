import re
from sys import stdin
from datetime import datetime, timedelta
from github import Github
from github.Issue import Issue
from msc_chart_generator.msc_chart import MSCChart, ChartType


TEXT = """
Here's your weekly spec update! The heart of Matrix is the specification - and this is modified by Matrix Spec Change (MSC) proposals. Learn more about how the process works at https://spec.matrix.org/proposals.


## MSC Status

**New MSCs:**
{new_mscs}

**MSCs in Final Comment Period:**
{mscs_in_fcp}

**Accepted MSCs:**
{accepted_mscs}

**Closed MSCs:**
{closed_mscs}

## Spec Updates
"""


def main():
    github_repo = "matrix-org/matrix-doc"
    github_token = ""
    g = Github(github_token)
    r = g.get_repo(github_repo)
    msc_chart = MSCChart(pygithub=g)
    msc_url_regex = re.compile(r"MSC([\d]{3,4})", re.IGNORECASE)

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
    closed_mscs = list(set(
        list(r.get_issues(
            state="closed",
            labels=["proposal", "rejected"],
            since=one_week_ago,
        )) +
        list(r.get_issues(
            state="closed",
            labels=["proposal", "obsolete"],
            since=one_week_ago,
        )) +
        list(r.get_issues(
            state="closed",
            labels=["proposal", "abandoned"],
            since=one_week_ago,
        ))
    ))
    postponed_mscs = list(r.get_issues(
        state="open",
        labels=["proposal", "finished-final-comment-period", "disposition-postpone"],
    ))
    accepted_mscs = [msc for msc in r.get_issues(
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
    accepted_mscs = [msc for msc in accepted_mscs if msc.closed_at > one_week_ago]
    closed_mscs = [msc for msc in closed_mscs if msc.closed_at > one_week_ago]

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

    if accepted_mscs:
        text = ""
        for msc in accepted_mscs:
            text += f"* [{msc.title}]({msc.html_url})\n"
        accepted_mscs = text.strip()
    else:
        accepted_mscs = "* *No MSCs were accepted this week.*"

    if closed_mscs:
        text = ""
        for msc in closed_mscs:
            text += f"* [{msc.title}]({msc.html_url})\n"
        closed_mscs = text.strip()
    else:
        closed_mscs = "* *No MSCs were closed/rejected this week.*"

    # Replace placeholders in template
    update_text = TEXT.format(
        new_mscs=new_mscs,
        mscs_in_fcp=mscs_in_fcp,
        accepted_mscs=accepted_mscs,
        closed_mscs=closed_mscs,
    )

    # Automatically replace MSCXXXX links in the Spec Core Team focus
    print("Input text to replace MSC links in (press Ctrl-D on an empty line when done):\n## Spec Updates")
    msc_descriptions = stdin.read()

    # Perform the substitution
    msc_descriptions = replace_mscs_not_in_brackets(msc_descriptions, github_repo)

    # Update the printed text with the substituted text
    update_text += msc_descriptions

    # Print it out for the user to copy-paste
    print("==============RENDERED TEXT BELOW==============")
    print(update_text)

    # Generate a chart of MSC progress
    # TODO: Broken, GitHub is sending back 500's.
    #msc_chart.generate(ChartType.STACKED_AREA, "stacked_area_chart.png")


def replace_mscs_not_in_brackets(input_str: str, github_repo: str) -> str:
    """Linkify instances of MSCXXXX if necessary, returning the new string.

    Instances of MSCXXXX which are already enclosed in square brackets (used for
    linking text in markdown) will be ignored.

    This function was mostly written by GPT-4.

    Args:
        input_str: The string to linkify instances of MSCXXXX in.
        github_repo: The GitHub repo to use for generating links, i.e.
            "matrix-org/matrix-spec-proposals".

    Returns:
        The linkified text.
    """
    msc_pattern = r'MSC\d{4}'

    output_str = ''
    bracket_depth = 0
    idx = 0

    while idx < len(input_str):
        if input_str[idx] == '[':
            bracket_depth += 1
            output_str += input_str[idx]
            idx += 1
        elif input_str[idx] == ']':
            bracket_depth -= 1
            output_str += input_str[idx]
            idx += 1
        else:
            msc_match = re.match(msc_pattern, input_str[idx:])
            if msc_match and bracket_depth == 0:
                msc_number = msc_match.group(0)[3:]
                replacement = f"[MSC{msc_number}](https://github.com/{github_repo}/issues/{msc_number})"
                output_str += replacement
                idx += len(msc_match.group(0))
            else:
                output_str += input_str[idx]
                idx += 1

    return output_str


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
