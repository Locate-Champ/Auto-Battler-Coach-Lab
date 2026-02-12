use rand_mt::Mt;

const TWO_POW_53: f64 = 9_007_199_254_740_992.0;

#[derive(Clone, Debug)]
pub struct PyRng {
    mt: Mt,
}

impl PyRng {
    pub fn seed_from_u64(seed: u64) -> Self {
        Self {
            mt: seeded_mt_from_u64(seed),
        }
    }

    pub fn reseed_from_u64(&mut self, seed: u64) {
        self.mt = seeded_mt_from_u64(seed);
    }

    pub fn random(&mut self) -> f64 {
        // CPython random.Random.random():
        // ((next_u32 >> 5) * 2**26 + (next_u32 >> 6)) / 2**53
        let a = (self.mt.next_u32() >> 5) as u64;
        let b = (self.mt.next_u32() >> 6) as u64;
        (((a << 26) + b) as f64) / TWO_POW_53
    }

    pub fn randbelow(&mut self, n: usize) -> usize {
        assert!(n > 0, "randbelow requires n > 0");
        // Matches CPython _randbelow_with_getrandbits: k = n.bit_length()
        let k = (usize::BITS - n.leading_zeros()) as usize;
        loop {
            let r = self.getrandbits_usize(k);
            if r < n {
                return r;
            }
        }
    }

    pub fn randrange_usize_stop(&mut self, stop: usize) -> usize {
        self.randbelow(stop)
    }

    pub fn randrange_usize(&mut self, start: usize, stop: usize) -> usize {
        assert!(stop > start, "randrange_usize requires stop > start");
        let width = stop - start;
        start + self.randbelow(width)
    }

    pub fn randrange_i32_stop(&mut self, stop: i32) -> i32 {
        self.randrange_i32(0, stop)
    }

    pub fn randrange_i32(&mut self, start: i32, stop: i32) -> i32 {
        assert!(stop > start, "randrange_i32 requires stop > start");
        let width = (stop - start) as usize;
        start + (self.randbelow(width) as i32)
    }

    pub fn randint_i32(&mut self, start: i32, stop_inclusive: i32) -> i32 {
        assert!(
            stop_inclusive >= start,
            "randint_i32 requires stop_inclusive >= start"
        );
        let width = (stop_inclusive - start + 1) as usize;
        start + (self.randbelow(width) as i32)
    }

    pub fn random_u64(&mut self) -> u64 {
        // CPython getrandbits packs 32-bit words little-endian:
        // first draw contributes low 32 bits.
        let low = self.mt.next_u32() as u64;
        let high = self.mt.next_u32() as u64;
        (high << 32) | low
    }

    pub fn shuffle<T>(&mut self, values: &mut [T]) {
        if values.len() <= 1 {
            return;
        }
        for i in (1..values.len()).rev() {
            let j = self.randbelow(i + 1);
            values.swap(i, j);
        }
    }

    fn getrandbits_usize(&mut self, k: usize) -> usize {
        if k == 0 {
            return 0;
        }

        let words = k.div_ceil(32);
        let mut remaining = k;
        let mut out: u128 = 0;

        for word_idx in 0..words {
            let mut word = self.mt.next_u32();
            if remaining < 32 {
                word >>= 32 - remaining;
            }
            out |= (word as u128) << (word_idx * 32);
            remaining = remaining.saturating_sub(32);
        }

        out as usize
    }
}

fn seeded_mt_from_u64(seed: u64) -> Mt {
    if seed == 0 {
        return Mt::new_with_key([0_u32]);
    }

    let low = seed as u32;
    let high = (seed >> 32) as u32;
    if high == 0 {
        Mt::new_with_key([low])
    } else {
        Mt::new_with_key([low, high])
    }
}

#[cfg(test)]
mod tests {
    use super::PyRng;

    #[test]
    fn test_random_seed_0_matches_python() {
        let mut rng = PyRng::seed_from_u64(0);
        let expected = [
            0.8444218515250481,
            0.7579544029403025,
            0.420571580830845,
            0.25891675029296335,
            0.5112747213686085,
        ];
        for value in expected {
            assert!((rng.random() - value).abs() < 1e-15);
        }
    }

    #[test]
    fn test_random_seed_42_matches_python() {
        let mut rng = PyRng::seed_from_u64(42);
        let expected = [
            0.6394267984578837,
            0.025010755222666936,
            0.27502931836911926,
            0.22321073814882275,
            0.7364712141640124,
        ];
        for value in expected {
            assert!((rng.random() - value).abs() < 1e-15);
        }
    }

    #[test]
    fn test_random_large_seed_matches_python() {
        let mut rng = PyRng::seed_from_u64(1_099_635_084_565);
        let expected = [
            0.17223907383219594,
            0.5477451027736541,
            0.8265339922475623,
        ];
        for value in expected {
            assert!((rng.random() - value).abs() < 1e-15);
        }
    }

    #[test]
    fn test_random_sequence_1000_matches_python_landmarks() {
        let mut rng = PyRng::seed_from_u64(42);
        let mut marks = [0.0_f64; 6];
        for i in 0..1000 {
            let value = rng.random();
            if i == 0 {
                marks[0] = value;
            } else if i == 1 {
                marks[1] = value;
            } else if i == 2 {
                marks[2] = value;
            } else if i == 9 {
                marks[3] = value;
            } else if i == 99 {
                marks[4] = value;
            } else if i == 999 {
                marks[5] = value;
            }
        }
        let expected = [
            0.6394267984578837,
            0.025010755222666936,
            0.27502931836911926,
            0.029797219438070344,
            0.8607797022344981,
            0.8554501933059546,
        ];
        for (got, want) in marks.iter().zip(expected.iter()) {
            assert!((got - want).abs() < 1e-15);
        }
    }

    #[test]
    fn test_randbelow_sequence_matches_python_randrange() {
        let mut rng = PyRng::seed_from_u64(0);
        let expected = [6_usize, 6, 0, 4, 8, 7, 6, 4, 7, 5];
        let got: Vec<usize> = (0..expected.len()).map(|_| rng.randbelow(10)).collect();
        assert_eq!(got, expected);
    }

    #[test]
    fn test_shuffle_matches_python() {
        let mut rng = PyRng::seed_from_u64(42);
        let mut values: Vec<i32> = (0..10).collect();
        rng.shuffle(&mut values);
        assert_eq!(values, vec![7, 3, 2, 8, 5, 6, 9, 4, 0, 1]);
    }
}
