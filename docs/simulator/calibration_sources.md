# TFT Set 16 Timing Measurement Videos

## How to Use

```bash
cd simulator/calibration
python youtube_measure.py "<URL>" --champion "<Name>"
```

---

## Priority 1: Critical Champions

### Kai'Sa (4-cost, 6-range)
| Video | Duration | Channel |
|-------|----------|---------|
| [Kai'Sa ⭐⭐⭐ 3 Star is UNSTOPPABLE](https://youtube.com/watch?v=A05CpIMAW28) | 8:55 | Narmer TFT |

```bash
python youtube_measure.py "https://youtube.com/watch?v=A05CpIMAW28" --champion "Kai'Sa"
```

### Xerath (5-cost, 4-range)
| Video | Duration | Channel |
|-------|----------|---------|
| [XERATH 1v9! ⭐⭐⭐](https://youtube.com/watch?v=EkF0oyN40Aw) | 14:17 | Lemuria TFT |
| [Perfect BUILD Xerath ⭐⭐⭐](https://youtube.com/watch?v=wwxJc1OM380) | 9:18 | Void TFT |
| [PRISMATIC SHURIMA 3 STAR XERATH](https://youtube.com/watch?v=pwziQpjha34) | 31:45 | Sunhide TFT |

```bash
python youtube_measure.py "https://youtube.com/watch?v=EkF0oyN40Aw" --champion "Xerath"
```

### Azir (5-cost, 4-range) - Also measure soldiers!
| Video | Duration | Channel |
|-------|----------|---------|
| [NEW AZIR GAMEPLAY in TFT SET 16](https://youtube.com/watch?v=-YsISQRo3Jk) | 20:42 | Redox |
| [FORCE AZIR To CLIMB](https://youtube.com/watch?v=B9mBQu7K_NY) | 22:32 | Redox |
| [I Highrolled Azir on 3-1](https://youtube.com/watch?v=jUwKNxMC1M8) | 30:10 | CammyTFT |

```bash
python youtube_measure.py "https://youtube.com/watch?v=-YsISQRo3Jk" --champion "Azir"
```

### Kindred (5-cost, 4-range)
| Video | Duration | Channel |
|-------|----------|---------|
| [KINDRED 1v9! ⭐⭐⭐](https://youtube.com/watch?v=uy7ZktpfoW8) | 11:48 | Lemuria TFT |
| [3 Star Kindred 1v9⭐⭐⭐](https://youtube.com/watch?v=zcad-CilgEY) | 11:18 | Yolo TFT |
| [MACHINE GUN KINDRED 5.0 AS](https://youtube.com/watch?v=QZixiu3D-Y4) | 21:00 | OzxFF |

```bash
python youtube_measure.py "https://youtube.com/watch?v=uy7ZktpfoW8" --champion "Kindred"
```

---

## Priority 2: High Value Champions

### Annie + Tibbers (5-cost) - MEASURE BOTH!
| Video | Duration | Channel |
|-------|----------|---------|
| [3 Star DARK CHILD! Annie + Tibbers](https://youtube.com/watch?v=3wu30ukEVT4) | 13:28 | Lemuria TFT |
| [FIRE HAZARD! 3 Star Annie and Tibbers](https://youtube.com/watch?v=9rXLsWvjSSw) | 31:43 | emilyywang |
| [3 STAR ANNIE AND TIBBERS!!](https://youtube.com/watch?v=nesW4v_ZZC8) | 0:55 | BlurredBerry |

```bash
# Measure Annie
python youtube_measure.py "https://youtube.com/watch?v=3wu30ukEVT4" --champion "Annie"
# Then measure Tibbers separately
python youtube_measure.py "https://youtube.com/watch?v=3wu30ukEVT4" --champion "Tibbers"
```

### Kalista (4-cost, 4-range)
| Video | Duration | Channel |
|-------|----------|---------|
| [This 3-Star Kalista Is TOO STRONG!](https://youtube.com/watch?v=FdpGeM2cvA8) | 10:32 | Yolo TFT |
| [How I Went From Kalista 0 To Kalista 3](https://youtube.com/watch?v=cKO-MaSqyUM) | 26:23 | BoxBox |
| [K3Soju Shows Why Kalista Is Underrated](https://youtube.com/watch?v=XlWU_Ya-HMY) | 0:31 | TFT Daily Clips |

```bash
python youtube_measure.py "https://youtube.com/watch?v=FdpGeM2cvA8" --champion "Kalista"
```

### Jhin (1-cost, 4-range)
| Video | Duration | Channel |
|-------|----------|---------|
| [How Toxic is Jhin ⭐⭐⭐ 3 Star](https://youtube.com/watch?v=F9h44kRd4mo) | 9:42 | Narmer TFT |
| [x3 Guinsoo Jhin⭐⭐⭐⭐4 Star](https://youtube.com/watch?v=zuKKqY_mzF0) | 11:14 | Yolo TFT |
| [Jhin's Infinite Range](https://youtube.com/watch?v=p8xycZ_iq8o) | 33:01 | leduckVODs |

```bash
python youtube_measure.py "https://youtube.com/watch?v=F9h44kRd4mo" --champion "Jhin"
```

---

## Priority 3: Medium Value Champions

### Malzahar (3-cost, 4-range) + Voidlings
| Video | Duration | Channel |
|-------|----------|---------|
| [Chinese Malzahar Reroll Comp](https://youtube.com/watch?v=64BUCyagZQ0) | 35:04 | shurkou |

```bash
python youtube_measure.py "https://youtube.com/watch?v=64BUCyagZQ0" --champion "Malzahar"
```

### Warwick (4-cost)
| Video | Duration | Channel |
|-------|----------|---------|
| [Warwick with Deathblade and RFC](https://youtube.com/watch?v=Tsba_SolZc0) | 33:14 | shurkou |

```bash
python youtube_measure.py "https://youtube.com/watch?v=Tsba_SolZc0" --champion "Warwick"
```

---

## Quick Reference: All Video URLs

```
# Priority 1 - Critical
Kai'Sa:   https://youtube.com/watch?v=A05CpIMAW28
Xerath:   https://youtube.com/watch?v=EkF0oyN40Aw
Azir:     https://youtube.com/watch?v=-YsISQRo3Jk
Kindred:  https://youtube.com/watch?v=uy7ZktpfoW8

# Priority 2 - High
Annie:    https://youtube.com/watch?v=3wu30ukEVT4
Kalista:  https://youtube.com/watch?v=FdpGeM2cvA8
Jhin:     https://youtube.com/watch?v=F9h44kRd4mo

# Priority 3 - Medium
Malzahar: https://youtube.com/watch?v=64BUCyagZQ0
```

---

## Measurement Tips

1. **Shorter videos** (8-15 min) are often better - more concentrated gameplay
2. **3-star showcases** usually have clean attack sequences
3. **Look for isolated fights** where you can clearly see one champion attacking
4. **Measure 5+ attacks** for accurate averages
5. **For summons** (Tibbers, Azir soldiers, Voidlings), measure them in a separate pass
