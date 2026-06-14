from django.test import TestCase

# Create your tests here.
# Django test case


class FactApiTestCase(TestCase):
    def test_fact_api(self):
        response = self.client.get("/googleFact")
        # check if the response is 200 OK.
        self.assertEqual(response.status_code, 200)

    def test_fact_api_keywords(self):
        response = self.client.get("/googleFact?keywords=corona,impfung")
        # check if the response is 200 OK.
        self.assertEqual(response.status_code, 200)
