# Calibration Comparison: Weighted vs Unweighted

| Metric | Weighted | Unweighted | Delta (W-U) |
|--------|---------:|-----------:|------------:|
| Brier Score | 0.2698 | 0.2134 | +0.0564 |
| Expected Calibration Error (ECE) | 0.2175 | 0.0347 | +0.1828 |

## Reliability Bins (Weighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 7.0 | 733.0 | 0.750 | 0.503 | 0.246 |
| 8.0 | 5180.0 | 0.891 | 0.678 | 0.213 |

## Reliability Bins (Unweighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 1.0 | 5.0 | 0.184 | 0.400 | 0.216 |
| 2.0 | 53.0 | 0.260 | 0.321 | 0.060 |
| 3.0 | 143.0 | 0.364 | 0.329 | 0.035 |
| 4.0 | 374.0 | 0.456 | 0.524 | 0.068 |
| 5.0 | 785.0 | 0.556 | 0.543 | 0.014 |
| 6.0 | 2267.0 | 0.660 | 0.623 | 0.036 |
| 7.0 | 2101.0 | 0.737 | 0.773 | 0.036 |
| 8.0 | 180.0 | 0.818 | 0.828 | 0.009 |
| 9.0 | 5.0 | 0.905 | 1.000 | 0.095 |

### Notes
- Brier score lower is better; ECE lower indicates closer calibration.
- Weighted model increases emphasis on latest season which may tighten reliability at higher probability bins.