#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void func()
{
	printf("Hello world\n");
}

void func2()
{
	printf("How did I get here?\n");
}


struct s_ops {
	void (* f) ();
};


int main()
{
	struct s_ops *a = (struct s_ops *) malloc(sizeof(struct s_ops));
	
	a->f = func;

	a->f();

	free(a); // use-after-free... free here, and use 'a' again later on

	struct s_ops *b = (struct s_ops *) malloc(sizeof(struct s_ops));
	b->f = func2;


	a->f();
	
}
