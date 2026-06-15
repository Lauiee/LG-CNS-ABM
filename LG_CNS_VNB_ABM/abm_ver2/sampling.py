import math
import random


DEFAULT_DISTRIBUTIONS = {
    "developer.skill_level": {
        "type": "lognormal",
        "median": {"context": "base_skill_level", "default": 1.4},
        "sigma": 0.18,
        "low": 0.5,
        "high": 3.0,
    },
    "developer.learning_rate": {
        "type": "beta",
        "alpha": 5.0,
        "beta": 5.0,
        "low": 0.1,
        "high": 0.9,
    },
    "developer.burnout_threshold": {
        "type": "truncated_normal",
        "mean": 20.0,
        "sd": 4.0,
        "low": 10.0,
        "high": 30.0,
    },
    "developer.quality_tendency": {
        "type": "lognormal",
        "median": 0.6,
        "sigma": 0.22,
        "low": 0.3,
        "high": 0.95,
    },
    "developer.interrupt_sensitivity": {
        "type": "beta",
        "alpha": 3.0,
        "beta": 5.0,
        "low": 0.1,
        "high": 0.8,
    },
    "developer.energy": {
        "type": "truncated_normal",
        "mean": 85.0,
        "sd": 8.0,
        "low": 0.0,
        "high": 100.0,
    },
    "developer.motivation": {
        "type": "truncated_normal",
        "mean": 70.0,
        "sd": 12.0,
        "low": 0.0,
        "high": 100.0,
    },
    "developer.knowledge": {
        "type": "truncated_normal",
        "mean": {"context": "skill_level", "multiplier": 20.0, "default": 30.0},
        "sd": 12.0,
        "low": 0.0,
        "high": 100.0,
    },
    "developer.flow_streak": {
        "type": "poisson",
        "lambda": 0.35,
        "low": 0,
        "high": 5,
    },
    "developer.accumulated_tech_debt": {
        "type": "gamma",
        "alpha": 3.0,
        "theta": 4.0,
        "low": 0.0,
        "high": 60.0,
    },
    "pl.leadership_style": {
        "type": "uniform",
        "low": 0.5,
        "high": 1.0,
    },
    "pl.team_awareness": {
        "type": "uniform",
        "low": 0.6,
        "high": 0.9,
    },
}


class ParameterSampler:
    def __init__(self, distributions=None, seed=None):
        self.rng = random.Random(seed)
        self.distributions = distributions if distributions is not None else DEFAULT_DISTRIBUTIONS

    def sample(self, name, default=None, context=None):
        spec = self.distributions.get(name)
        if spec is None:
            return default

        context = context or {}
        dist_type = spec.get("type", spec.get("distribution", "constant"))
        low = self._resolve(spec.get("low"), None, context)
        high = self._resolve(spec.get("high"), None, context)

        if dist_type == "constant":
            value = self._resolve(spec.get("value"), default, context)
            return self._clamp(value, low, high)
        if dist_type == "uniform":
            value = self._sample_uniform(spec, default, context, low, high)
            return self._clamp(value, low, high)
        if dist_type == "normal":
            return self._sample_normal(spec, default, context, low, high)
        if dist_type == "truncated_normal":
            return self._sample_truncated_normal(spec, default, context, low, high)
        if dist_type == "beta":
            value = self._sample_beta(spec, context, low, high)
            return self._clamp(value, low, high)
        if dist_type == "lognormal":
            return self._sample_lognormal(spec, default, context, low, high)
        if dist_type == "gamma":
            return self._sample_gamma(spec, default, context, low, high)
        if dist_type == "poisson":
            value = self._sample_poisson(spec, context)
            return int(self._clamp(value, low, high))
        if dist_type == "categorical":
            return self._sample_categorical(spec, default, context)

        return default

    def _sample_uniform(self, spec, default, context, low, high):
        min_value = self._resolve(spec.get("min"), low, context)
        max_value = self._resolve(spec.get("max"), high, context)
        if min_value is None or max_value is None:
            return default
        return self.rng.uniform(min_value, max_value)

    def _sample_normal(self, spec, default, context, low, high):
        mean = self._resolve(spec.get("mean"), default, context)
        sd = self._resolve(spec.get("sd", spec.get("sigma", spec.get("std", 1.0))), 1.0, context)
        if mean is None:
            return default
        return self._bounded(lambda: self.rng.normalvariate(mean, sd), low, high)

    def _sample_truncated_normal(self, spec, default, context, low, high):
        mean = self._resolve(spec.get("mean"), default, context)
        sd = self._resolve(spec.get("sd", spec.get("sigma", spec.get("std", 1.0))), 1.0, context)
        if mean is None:
            return default
        return self._bounded(lambda: self.rng.normalvariate(mean, sd), low, high)

    def _sample_beta(self, spec, context, low, high):
        alpha = self._resolve(spec.get("alpha", 1.0), 1.0, context)
        beta = self._resolve(spec.get("beta", 1.0), 1.0, context)
        raw = self.rng.betavariate(alpha, beta)
        if low is None or high is None:
            return raw
        return low + raw * (high - low)

    def _sample_lognormal(self, spec, default, context, low, high):
        median = self._resolve(spec.get("median"), None, context)
        sigma = self._resolve(spec.get("sigma", 0.25), 0.25, context)
        if median is not None and median > 0:
            mu = math.log(median)
        else:
            mu = self._resolve(spec.get("mu"), None, context)
            if mu is None:
                mean = self._resolve(spec.get("mean"), default, context)
                if mean is None or mean <= 0:
                    return default
                mu = math.log(mean) - (sigma * sigma / 2)
        return self._bounded(lambda: self.rng.lognormvariate(mu, sigma), low, high)

    def _sample_gamma(self, spec, default, context, low, high):
        alpha = self._resolve(spec.get("alpha", spec.get("shape")), None, context)
        theta = self._resolve(spec.get("theta", spec.get("scale")), None, context)
        if alpha is None or theta is None:
            mean = self._resolve(spec.get("mean"), default, context)
            if mean is None:
                return default
            alpha = 3.0
            theta = mean / alpha
        return self._bounded(lambda: self.rng.gammavariate(alpha, theta), low, high)

    def _sample_poisson(self, spec, context):
        lam = self._resolve(spec.get("lambda", spec.get("lam", 1.0)), 1.0, context)
        if lam <= 0:
            return 0

        threshold = math.exp(-lam)
        k = 0
        product = 1.0
        while product > threshold:
            k += 1
            product *= self.rng.random()
        return k - 1

    def _sample_categorical(self, spec, default, context):
        choices = self._resolve(spec.get("choices"), None, context)
        if not choices:
            return default

        if isinstance(choices, dict):
            values = list(choices.keys())
            weights = list(choices.values())
        else:
            values = []
            weights = []
            for item in choices:
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    values.append(item[0])
                    weights.append(item[1])
                else:
                    values.append(item)
                    weights.append(1.0)

        total = sum(weights)
        if total <= 0:
            return default

        draw = self.rng.random() * total
        cumulative = 0.0
        for value, weight in zip(values, weights):
            cumulative += weight
            if draw <= cumulative:
                return value
        return values[-1]

    def _bounded(self, draw, low, high, attempts=100):
        value = None
        for _ in range(attempts):
            value = draw()
            if self._in_bounds(value, low, high):
                return value
        return self._clamp(value, low, high)

    def _in_bounds(self, value, low, high):
        if low is not None and value < low:
            return False
        if high is not None and value > high:
            return False
        return True

    def _clamp(self, value, low, high):
        if value is None:
            return value
        if low is not None and value < low:
            return low
        if high is not None and value > high:
            return high
        return value

    def _resolve(self, value, default, context):
        if value is None:
            return default
        if callable(value):
            return value(context)
        if isinstance(value, dict) and "context" in value:
            resolved = context.get(value["context"], value.get("default", default))
            if resolved is None:
                return default
            resolved = resolved * value.get("multiplier", 1.0)
            resolved = resolved + value.get("offset", 0.0)
            return resolved
        if isinstance(value, str) and value in context:
            return context[value]
        return value
