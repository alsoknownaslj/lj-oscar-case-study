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
model. Computed here as average precision (scikit-learn's `average_precision_score`),
the standard step-wise estimate of that area.

## Calibration

Whether a predicted probability means what it says: of the members scored at about 10%,
do about 10% turn out to have the condition? Checked by sorting test members into ten
equal-sized bins by predicted probability and comparing each bin's average prediction
with its observed rate. Points above the diagonal mean the model under-predicts; below,
it over-predicts. It matters here because the rx-only scoring hands out probabilities
and expected counts, which are only as good as the calibration.

## Lift vs independence

How much more often two things co-occur than they would if they were unrelated:
observed count divided by expected count, where expected = row total × column total ÷
grand total. 1.0 means no relationship, 6.0 means six times the chance level, and 0.1
means the pair is strongly avoided. Used for the claims-tier × fill-tier table and the
condition × drug-class pairs.

## Head/tail breaks

A way to cut heavy-tailed counts into tiers: split at the mean, then split the
above-mean group at its own mean. The cuts are means rather than data values, so
thousands of members tied at exactly 1 or 2 claim lines can't collapse a tier the way
they collapse quartiles. Here two cuts give low / med / high among members with any
activity, and zero is its own tier.

## Logistic regression (L2, one-vs-rest)

The model behind requirement 2. For one condition it learns a weight per feature and
turns a member's weighted sum into a probability:
`p = 1 / (1 + e^-(b + w1·x1 + … + wk·xk))`. A positive weight means more fills of that
drug class push the probability up. L2 regularization penalizes large weights so a rare
drug class can't pick up a big weight from noise. One-vs-rest means a separate model per
condition, because members can have several conditions at once.
