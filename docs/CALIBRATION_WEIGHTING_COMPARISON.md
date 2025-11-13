# Calibration Comparison: Weighted vs Unweighted

| Metric | Weighted | Unweighted | Delta (W-U) |
|--------|---------:|-----------:|------------:|
| Brier Score | 0.2287 | 0.2271 | +0.0016 |
| Expected Calibration Error (ECE) | 0.0062 | 0.0892 | -0.0830 |

## Reliability Bins (Weighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 5.0 | 683.0 | 0.534 | 0.486 | 0.048 |
| 6.0 | 4745.0 | 0.657 | 0.657 | 0.000 |
| 7.0 | 1.0 | 0.733 | 1.000 | 0.267 |

## Reliability Bins (Unweighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 1.0 | 40.0 | 0.156 | 0.375 | 0.219 |
| 2.0 | 155.0 | 0.261 | 0.342 | 0.081 |
| 3.0 | 410.0 | 0.355 | 0.493 | 0.137 |
| 4.0 | 700.0 | 0.457 | 0.521 | 0.065 |
| 5.0 | 2432.0 | 0.559 | 0.619 | 0.060 |
| 6.0 | 1530.0 | 0.638 | 0.767 | 0.129 |
| 7.0 | 146.0 | 0.726 | 0.829 | 0.102 |
| 8.0 | 16.0 | 0.838 | 1.000 | 0.162 |

### Notes
- Brier score lower is better; ECE lower indicates closer calibration.
- Weighted model increases emphasis on latest season which may tighten reliability at higher probability bins.