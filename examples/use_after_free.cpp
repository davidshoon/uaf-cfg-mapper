#include <cstdlib>

int malloc_bug(bool release) {
    int *p = static_cast<int *>(std::malloc(sizeof(int)));
    if (!p) return 0;
    *p = 42;
    int *alias = p;
    if (release) std::free(p);
    return *alias; // possible use after free through an alias
}

int new_bug() {
    int *p = new int(7);
    delete p;
    return *p; // use after delete
}

int safe() {
    int *p = new int(7);
    int result = *p;
    delete p;
    return result;
}
