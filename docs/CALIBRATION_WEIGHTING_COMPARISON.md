# Calibration Comparison: Weighted vs Unweighted

| Metric | Weighted | Unweighted | Delta (W-U) |
|--------|---------:|-----------:|------------:|
| Brier Score | 0.2337 | 0.2279 | +0.0058 |
| Expected Calibration Error (ECE) | 0.0503 | 0.0832 | -0.0329 |

## Reliability Bins (Weighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 2.0 | 3.0 | 0.233 | 0.333 | 0.100 |
| 3.0 | 1.0 | 0.306 | 0.000 | 0.306 |
| 5.0 | 687.0 | 0.562 | 0.480 | 0.082 |
| 6.0 | 4859.0 | 0.692 | 0.646 | 0.046 |
| 7.0 | 12.0 | 0.736 | 0.833 | 0.097 |

## Reliability Bins (Unweighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 0.0 | 1.0 | 0.087 | 0.000 | 0.087 |
| 1.0 | 48.0 | 0.158 | 0.271 | 0.113 |
| 2.0 | 188.0 | 0.260 | 0.351 | 0.091 |
| 3.0 | 371.0 | 0.354 | 0.485 | 0.131 |
| 4.0 | 697.0 | 0.458 | 0.495 | 0.037 |
| 5.0 | 2674.0 | 0.559 | 0.620 | 0.061 |
| 6.0 | 1455.0 | 0.633 | 0.767 | 0.134 |
| 7.0 | 117.0 | 0.734 | 0.786 | 0.052 |
| 8.0 | 11.0 | 0.840 | 1.000 | 0.160 |

### Notes
- Brier score lower is better; ECE lower indicates closer calibration.
- Weighted model increases emphasis on latest season which may tighten reliability at higher probability bins.