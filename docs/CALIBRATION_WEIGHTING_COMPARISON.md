# Calibration Comparison: Weighted vs Unweighted

| Metric | Weighted | Unweighted | Delta (W-U) |
|--------|---------:|-----------:|------------:|
| Brier Score | 0.2552 | 0.2269 | +0.0283 |
| Expected Calibration Error (ECE) | 0.1620 | 0.0882 | +0.0738 |

## Reliability Bins (Weighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 1.0 | 1.0 | 0.149 | 1.000 | 0.851 |
| 6.0 | 693.0 | 0.644 | 0.470 | 0.174 |
| 7.0 | 5.0 | 0.776 | 0.800 | 0.024 |
| 8.0 | 4842.0 | 0.815 | 0.655 | 0.160 |

## Reliability Bins (Unweighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 0.0 | 5.0 | 0.090 | 0.400 | 0.310 |
| 1.0 | 56.0 | 0.170 | 0.375 | 0.205 |
| 2.0 | 166.0 | 0.259 | 0.355 | 0.096 |
| 3.0 | 381.0 | 0.355 | 0.438 | 0.084 |
| 4.0 | 769.0 | 0.459 | 0.524 | 0.065 |
| 5.0 | 2474.0 | 0.558 | 0.621 | 0.063 |
| 6.0 | 1518.0 | 0.635 | 0.767 | 0.132 |
| 7.0 | 156.0 | 0.725 | 0.846 | 0.121 |
| 8.0 | 16.0 | 0.859 | 1.000 | 0.141 |

### Notes
- Brier score lower is better; ECE lower indicates closer calibration.
- Weighted model increases emphasis on latest season which may tighten reliability at higher probability bins.