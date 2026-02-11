/// Combat data loader - parses combat_data.json for champion stats, abilities, items.
use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

/// Loaded and parsed combat data for all champions.
#[derive(Debug, Clone)]
pub struct CombatData {
    pub champions: HashMap<String, Value>,
}

impl CombatData {
    /// Load combat data from a JSON file.
    pub fn load(path: &Path) -> Result<Self, String> {
        let content =
            fs::read_to_string(path).map_err(|e| format!("Failed to read combat data: {}", e))?;
        let data: Value = serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse combat data JSON: {}", e))?;

        let mut champions = HashMap::new();

        // combat_data.json has a nested "champions" key: {"champions": {"TFT16_Ekko": {...}, ...}}
        let champ_data = data.get("champions").unwrap_or(&data); // Fall back to root if no "champions" key

        if let Value::Object(map) = champ_data {
            for (key, value) in map {
                champions.insert(key.clone(), value.clone());
            }
        } else {
            return Err("No champions data found in combat_data.json".to_string());
        }

        Ok(Self { champions })
    }

    /// Get champion data by API name.
    pub fn get_champion(&self, api_name: &str) -> Option<&Value> {
        self.champions.get(api_name)
    }
}

/// Helper to extract a value from a star-level array [0, 1star, 2star, 3star].
/// Falls back to `default` if the index is missing or the data isn't an array.
#[inline]
pub fn star_val(var: &Value, star: i32, default: f64) -> f64 {
    match var {
        Value::Array(arr) => arr
            .get(star as usize)
            .and_then(|v| v.as_f64())
            .unwrap_or(default),
        Value::Number(n) => n.as_f64().unwrap_or(default),
        _ => default,
    }
}

/// Helper to get a float from a JSON value.
#[inline]
pub fn get_f64(val: &Value, key: &str, default: f64) -> f64 {
    val.get(key).and_then(|v| v.as_f64()).unwrap_or(default)
}

/// Helper to get an int from a JSON value.
#[inline]
pub fn get_i64(val: &Value, key: &str, default: i64) -> i64 {
    val.get(key).and_then(|v| v.as_i64()).unwrap_or(default)
}

/// Helper to get a string from a JSON value.
#[inline]
pub fn get_str<'a>(val: &'a Value, key: &str, default: &'a str) -> &'a str {
    val.get(key).and_then(|v| v.as_str()).unwrap_or(default)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_star_val_array() {
        let val = serde_json::json!([0, 100, 200, 300]);
        assert_eq!(star_val(&val, 1, 0.0), 100.0);
        assert_eq!(star_val(&val, 2, 0.0), 200.0);
        assert_eq!(star_val(&val, 3, 0.0), 300.0);
    }

    #[test]
    fn test_star_val_scalar() {
        let val = serde_json::json!(42.5);
        assert_eq!(star_val(&val, 1, 0.0), 42.5);
    }

    #[test]
    fn test_star_val_out_of_bounds() {
        let val = serde_json::json!([0, 100]);
        assert_eq!(star_val(&val, 5, 99.0), 99.0);
    }
}
