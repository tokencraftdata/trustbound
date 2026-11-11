# arXiv submission guide — 9 November 2026

Author: **Sandip Nandi — Independent Researcher**. Target: submit by
**30 November 2026**. The author reports an arXiv account and endorsement. The endorsement domain
has not been independently inspected. Public release and submission remain
on hold at the author's request; no paper or artifact has been published.

## Recommended category

Use **cs.CR (Cryptography and Security)** as primary and request **cs.LO (Logic
in Computer Science)** as a cross-list. This is our classification judgment:
the central question concerns authorization, mediation and trustworthy payment
evidence; Lean and transition-system reasoning provide the method. The
[official taxonomy](https://arxiv.org/category_taxonomy) covers security under
cs.CR and program verification under cs.LO. Travel agents motivate the work;
the contribution is not an AI learning algorithm. Moderators decide placement.

## Recommended licenses

For the **paper**, use the **arXiv.org perpetual, non-exclusive license 1.0**.
It allows arXiv to distribute the preprint while leaving broader reuse rights
ungranted. This is a cautious choice while later publication venues remain
undecided; it does not guarantee compatibility with every venue. **CC BY 4.0**
is the alternative if the author wants broad attributed reuse, including
commercial adaptation. A posted version's license is irrevocable; choose it in
the submission form after checking the rights to grant it.
[Official license guidance](https://info.arxiv.org/help/license/index.html).

For the **selected software artifact**, recommend **MIT** for author-owned code
and its documentation. MIT permits reuse, modification and commercial use with
its notice retained. This is a separate choice from the paper license.
[MIT terms](https://opensource.org/license/mit).
Neither recommendation has been applied as a license grant. Third-party
packages and the conference style retain their own terms; the selected-core
archive bundles neither dependencies nor the conference template.

## Account and endorsement

The author reports that the account is created and endorsement obtained.
Before submission, check that the account permits the chosen cs.CR category;
the endorsement domain has not been independently inspected. Endorsement is
submission eligibility, not peer-review approval.
[Official endorsement guidance](https://info.arxiv.org/help/endorsement.html).

## Disclosure and metadata

Both manuscripts disclose assistance from OpenAI ChatGPT and Codex in
literature exploration, code development, and drafting and editing. The author
retains responsibility for the paper and artifact. This follows arXiv's
[generative-AI policy](https://info.arxiv.org/help/moderation/index.html).
The copyable title, abstract, and comments use ASCII characters as required by
[arXiv's metadata guidance](https://info.arxiv.org/help/prep.html).

## Artifact access

The private GitHub repository is a working copy, not public reader access.
The prepared `TrustBound_Core_Artifact.zip` isolates the paper's existing core
without provider probes, credentials, raw provider records, account details,
conference template, or unrelated research. Its README explains what running it
achieves; its manifest pins every packaged file. It currently retains a
rights-pending notice and must not be described as an open-source release.

Recommended release: publish this frozen selected-core package with the agreed
software terms, retain its checksum and version, and add its stable public URL
to the author manuscript. Keep the broader working repository private unless
the author deliberately changes that decision. The final review requests a DOI-backed archive specifically. The Zenodo
deposit candidate is prepared in `release/`. Publication approval, deposit-account
access, and the software-license choice remain pending. Verify public download and its checksum after
publication, then cite the issued version DOI in Appendix A.

Alternatively, arXiv supports code/data under an `anc/` folder in a TeX source
submission. These files become part of the public version; they cannot be
updated independently of the paper. Do not put manuscript TeX under `anc/`.
[Ancillary-file instructions](https://info.arxiv.org/help/ancillary_files.html).

The conference review copy must use the venue's permitted anonymous artifact
route. Do not insert an identifying private GitHub link into that copy. Until
access is resolved, its availability statement says that an anonymous artifact
link and public release terms are pending. The current PDFs do not promise an existing public artifact.

## Upload sequence

Use `arxiv-metadata.json` for the title, author and abstract. Its category and
license fields are recommendations, not evidence of completed form choices.
Upload **TrustBound_arXiv_Source.zip**, not the anonymous conference PDF.
The manuscript was created in LaTeX, so submit its sources and figures.
Inspect arXiv's own processed PDF, metadata and references. Complete the
account's rights declarations and final submission as the author. Do not add a
journal reference, acceptance claim, DOI or arXiv identifier that does not exist.
[Submission instructions](https://info.arxiv.org/help/submit/index.html).

License selection, public artifact access with a verified version DOI, and
the processed-PDF check remain the final steps. Account and endorsement are
reported complete. Obtain the author's approval before any public release or
submission. Local compilation is not an arXiv processing test, and submission does not guarantee
moderation acceptance. No new provider integration is needed for this note.

## Anonymous reviewer access

If the selected venue permits it, [Anonymous GitHub](https://anonymous.4open.science/)
is a possible route for an anonymous review copy. No mirror has been created.
Before using that route, prepare the selected artifact, inspect the served files
for identifying content, and verify the reviewer link. Use the actual verified
artifact URL in the review paper, not the service homepage. Publication remains
on hold pending the author's approval.

The author paper currently links the private working repository and explicitly
states its access status. This is a pointer, not a substitute for public artifact
access or the DOI-backed release requested in the review.
