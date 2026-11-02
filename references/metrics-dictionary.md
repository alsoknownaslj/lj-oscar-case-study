# Metrics dictionary

Plain definitions of the statistical concepts this project's reports lean on. One entry
per concept, in the register Lauren asked for: what it is, why it's used here, a small
formula only where it earns its keep, and every acronym spelled out once. Add an entry
the first time a report or notebook uses the concept; when it's unclear whether a concept
earns an entry, ask Lauren rather than deciding alone (`soul.md`, The craft).

## AUROC — area under the receiver operating characteristic curve

How well the model ranks: the probability that a random member who has the condition
scores higher than a random member who doesn't. 0.5 means coin-flipping, 1.0 means
perfect ranking. Prevalence doesn't move it, so a high AUROC can sit on top of terrible
precision when positives are rare; that gap is what AUPRC catches.

## AUPRC — area under the precision-recall curve

Of the members the model flags, how many truly have the condition, averaged as the
flagging threshold sweeps from strict to loose. Its natural baseline is the condition's
prevalence, so the two get quoted together — "AUPRC 0.41 against a 0.03 baseline" reads
honestly, "AUPRC 0.41" alone doesn't (numbers illustrative). Preferred headline metric
here because most conditions are rare, and accuracy or AUROC alone would flatter the
model.
