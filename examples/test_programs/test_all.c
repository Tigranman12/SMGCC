int fact(int n) {
    if (n < 2) return 1;
    return n * fact(n - 1);
}

int fib(int n) {
    if (n < 2) return n;
    return fib(n - 1) + fib(n - 2);
}

int main() {
    int i = 0;
    int sum = 0;
    for (i = 1; i <= 10; i = i + 1) {
        sum = sum + i;
    }

    int f5 = fact(5);
    int fib10 = fib(10);

    int result = sum + f5 + fib10;
    return result;
}
