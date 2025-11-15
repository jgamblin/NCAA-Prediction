# Calibration Comparison: Weighted vs Unweighted

| Metric | Weighted | Unweighted | Delta (W-U) |
|--------|---------:|-----------:|------------:|
| Brier Score | 0.2466 | 0.2267 | +0.0199 |
| Expected Calibration Error (ECE) | 0.1227 | 0.0785 | +0.0442 |

## Reliability Bins (Weighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 6.0 | 678.0 | 0.614 | 0.462 | 0.152 |
| 7.0 | 4768.0 | 0.763 | 0.645 | 0.118 |

## Reliability Bins (Unweighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 1.0 | 40.0 | 0.169 | 0.225 | 0.056 |
| 2.0 | 168.0 | 0.264 | 0.315 | 0.052 |
| 3.0 | 349.0 | 0.357 | 0.476 | 0.119 |
| 4.0 | 820.0 | 0.457 | 0.473 | 0.016 |
| 5.0 | 2511.0 | 0.558 | 0.625 | 0.067 |
| 6.0 | 1374.0 | 0.635 | 0.769 | 0.134 |
| 7.0 | 173.0 | 0.727 | 0.780 | 0.054 |
| 8.0 | 11.0 | 0.855 | 1.000 | 0.145 |

### Notes
- Brier score lower is better; ECE lower indicates closer calibration.
- Weighted model increases emphasis on latest season which may tighten reliability at higher probability bins.