int fact(int n) {
    if (n < 2) return 1;
    return n * fact(n - 1);
}

int main() {
    int total = 0;
    int i = 1;
    while (i <= 5) {
        total = total + fact(i);
        i = i + 1;
    }
    return total;
}
