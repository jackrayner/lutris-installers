# Security Policy

`lutris-installers` is a small, solo-maintained hobby project. This policy is deliberately lightweight: there's no security team, no SLA and no bug bounty, just one maintainer doing their best.

## Reporting a vulnerability

Please report security issues privately using GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability): go to this repo's **Security** tab and click **Report a vulnerability**. This is the preferred and only channel for reports. There's no monitored security email address for this project, so please don't send one.

You should get a response within a few days, but given this is a one-person project in spare time, there's no guaranteed turnaround.

## Supported versions

Only the latest commit on `main` is supported. There are no release branches and no backports.

## Scope

In scope: the install scripts and workflows in this repo. For example, a script that could run unintended commands, tamper with a download, or skip checksum verification.

Out of scope: [Lutris](https://lutris.net/), Wine and Proton, the D2DX Glide wrapper (report that to [`jackrayner/d2dx`](https://github.com/jackrayner/d2dx), or to [`bolrog/d2dx`](https://github.com/bolrog/d2dx) for upstream code), the games themselves, and Blizzard's patch downloads. Those are separate projects with their own maintainers.
