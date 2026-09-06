from django.shortcuts import render


def review_list(request):

	return render(
		request,
		'reviews/review_list.html',
		{'reviews': []}
	)

# Create your views here.
