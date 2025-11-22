# Calibration Comparison: Weighted vs Unweighted

| Metric | Weighted | Unweighted | Delta (W-U) |
|--------|---------:|-----------:|------------:|
| Brier Score | 0.2444 | 0.2265 | +0.0179 |
| Expected Calibration Error (ECE) | 0.1231 | 0.0883 | +0.0348 |

## Reliability Bins (Weighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 6.0 | 687.0 | 0.626 | 0.488 | 0.138 |
| 7.0 | 4808.0 | 0.775 | 0.654 | 0.121 |

## Reliability Bins (Unweighted)
| Bin | Count | Pred Mean | Outcome Mean | Abs Gap |
|-----|------:|----------:|-------------:|--------:|
| 1.0 | 29.0 | 0.164 | 0.379 | 0.215 |
| 2.0 | 171.0 | 0.261 | 0.368 | 0.107 |
| 3.0 | 376.0 | 0.353 | 0.471 | 0.118 |
| 4.0 | 764.0 | 0.459 | 0.497 | 0.038 |
| 5.0 | 2485.0 | 0.557 | 0.631 | 0.074 |
| 6.0 | 1518.0 | 0.636 | 0.758 | 0.122 |
| 7.0 | 134.0 | 0.721 | 0.843 | 0.122 |
| 8.0 | 18.0 | 0.847 | 1.000 | 0.153 |

### Notes
- Brier score lower is better; ECE lower indicates closer calibration.
- Weighted model increases emphasis on latest season which may tighten reliability at higher probability bins.