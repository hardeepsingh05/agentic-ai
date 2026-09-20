#!/usr/bin/env python3
"""
Calculate the first 1,000,000 terms of the series: 1 - 1/3 + 1/5 - 1/7 + ...
Multiply the total by 4 to approximate pi.
This is the Leibniz formula for pi: pi = 4 * (1 - 1/3 + 1/5 - 1/7 + ...)
"""

def calculate_pi_leibniz(num_terms):
    """
    Calculate pi using the Leibniz formula.
    
    The series is: pi/4 = 1 - 1/3 + 1/5 - 1/7 + 1/9 - ...
    So: pi = 4 * (1 - 1/3 + 1/5 - 1/7 + ...)
    
    Args:
        num_terms: Number of terms to include in the series
    
    Returns:
        Approximation of pi
    """
    pi_over_4 = 0.0
    
    for i in range(num_terms):
        term = 1.0 / (2 * i + 1)  # Denominator is 1, 3, 5, 7, ...
        if i % 2 == 1:  # Odd terms are negative
            term = -term
        pi_over_4 += term
    
    return 4 * pi_over_4


def main():
    num_terms = 1_000_000
    
    print(f"Calculating pi using the Leibniz formula with {num_terms:,} terms...")
    print(f"Series: 1 - 1/3 + 1/5 - 1/7 + ...")
    print()
    
    result = calculate_pi_leibniz(num_terms)
    
    print(f"Result after multiplying by 4: {result}")
    print(f"Actual value of pi:           3.141592653589793...")
    print(f"Difference from pi:           {abs(result - 3.141592653589793):.10f}")


if __name__ == "__main__":
    main()