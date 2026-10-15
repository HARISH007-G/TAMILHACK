import unittest
import json
import os
import sys

# Ensure UTF-8 output encoding for test runs
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app import app
import atlas_service

class TestVoiceToVillageAtlas(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_atlas_page_renders_200(self):
        """Test that the /atlas route renders successfully with 200 OK."""
        response = self.client.get('/atlas')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Voice-to-Village Atlas", html)
        self.assertIn("ஒவ்வொரு ஊருக்கும் ஒரு குரல்", html)
        self.assertIn("google.maps", html)
        self.assertIn("atlasMap", html)

    def test_get_atlas_locations_all(self):
        """Test /api/atlas/locations returns a non-empty list of verified locations."""
        response = self.client.get('/api/atlas/locations')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertTrue(data.get('success'))
        locations = data.get('locations', [])
        self.assertIsInstance(locations, list)
        self.assertGreater(len(locations), 0)
        
        # Check properties of a location
        first = locations[0]
        self.assertIn('id', first)
        self.assertIn('name', first)
        self.assertIn('name_ta', first)
        self.assertIn('district', first)
        self.assertIn('latitude', first)
        self.assertIn('longitude', first)
        self.assertIn('story_count', first)

    def test_get_atlas_locations_filter_district(self):
        """Test filtering locations by district."""
        response = self.client.get('/api/atlas/locations?district=மதுரை')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertTrue(data.get('success'))
        for loc in data.get('locations', []):
            self.assertIn(loc['district'], ['மதுரை', 'Madurai'])

    def test_get_atlas_locations_filter_query(self):
        """Test searching locations by name or district."""
        response = self.client.get('/api/atlas/locations?q=Bhavani')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertTrue(data.get('success'))
        self.assertTrue(any('bhavani' in (loc.get('name_en', '') or '').lower() or 'பவானி' in loc['name'] for loc in data.get('locations', [])))

    def test_get_location_stories(self):
        """Test fetching stories for a specific location."""
        # Get all locations first to pick one with story_count > 0
        loc_resp = self.client.get('/api/atlas/locations')
        loc_data = json.loads(loc_resp.get_data(as_text=True))
        loc_with_stories = next((l for l in loc_data['locations'] if l['story_count'] > 0), None)
        
        if loc_with_stories:
            loc_id = loc_with_stories['id']
            response = self.client.get(f'/api/atlas/locations/{loc_id}/stories')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.get_data(as_text=True))
            self.assertTrue(data.get('success'))
            self.assertIn('location', data)
            self.assertIn('stories', data)
            self.assertGreater(len(data['stories']), 0)
            
            first_story = data['stories'][0]
            self.assertIn('id', first_story)
            self.assertIn('title', first_story)
            self.assertIn('tamil_text', first_story)
        else:
            self.skipTest("No location currently has stories linked.")

    def test_get_story_details(self):
        """Test fetching complete story details by ID."""
        # Pick any story from an active location
        loc_resp = self.client.get('/api/atlas/locations')
        loc_data = json.loads(loc_resp.get_data(as_text=True))
        loc_with_stories = next((l for l in loc_data['locations'] if l['story_count'] > 0), None)
        
        if loc_with_stories:
            stories_resp = self.client.get(f'/api/atlas/locations/{loc_with_stories["id"]}/stories')
            stories_data = json.loads(stories_resp.get_data(as_text=True))
            story_id = stories_data['stories'][0]['id']
            
            response = self.client.get(f'/api/atlas/stories/{story_id}')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.get_data(as_text=True))
            self.assertTrue(data.get('success'))
            story = data.get('story')
            self.assertIsNotNone(story)
            self.assertEqual(story['id'], story_id)
            self.assertIn('title', story)
            self.assertIn('tamil_text', story)
            self.assertIn('vocabulary', story)
            self.assertIn('primary_location', story)
        else:
            self.skipTest("No story found to test.")

    def test_get_story_related_and_evidence(self):
        """Test related stories endpoint returns connection reasons/evidence."""
        loc_resp = self.client.get('/api/atlas/locations')
        loc_data = json.loads(loc_resp.get_data(as_text=True))
        loc_with_stories = next((l for l in loc_data['locations'] if l['story_count'] > 0), None)
        
        if loc_with_stories:
            stories_resp = self.client.get(f'/api/atlas/locations/{loc_with_stories["id"]}/stories')
            stories_data = json.loads(stories_resp.get_data(as_text=True))
            story_id = stories_data['stories'][0]['id']
            
            response = self.client.get(f'/api/atlas/stories/{story_id}/related')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.get_data(as_text=True))
            self.assertTrue(data.get('success'))
            self.assertIn('related', data)
            for item in data['related']:
                self.assertIn('connection_reason', item)
                self.assertIn('evidence', item)
                self.assertIn('shared_elements', item)

    def test_get_story_constellation(self):
        """Test the global Story Constellation graph endpoint."""
        response = self.client.get('/api/atlas/constellation')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertTrue(data.get('success'))
        self.assertIn('nodes', data)
        self.assertIn('links', data)
        self.assertIsInstance(data['nodes'], list)
        self.assertIsInstance(data['links'], list)
        
        if len(data['links']) > 0:
            link = data['links'][0]
            self.assertIn('source', link)
            self.assertIn('target', link)
            self.assertIn('reason', link)
            self.assertIn('evidence', link)

    def test_gazetteer_coordinate_verification(self):
        """Verify that all locations in Tamil Nadu gazetteer fall within real geographic bounds."""
        for place, info in atlas_service.TN_COORDINATES.items():
            lat = info['lat']
            lng = info['lng']
            # Tamil Nadu approximate bounding box: Lat 8.0 to 13.6, Lng 76.2 to 80.4
            self.assertTrue(8.0 <= lat <= 14.0, f"Latitude for {place} ({lat}) out of Tamil Nadu bounds")
            self.assertTrue(76.0 <= lng <= 80.8, f"Longitude for {place} ({lng}) out of Tamil Nadu bounds")
            self.assertTrue(len(info['name_ta']) > 0, f"Missing Tamil name for {place}")
            self.assertTrue(len(info['district']) > 0, f"Missing District for {place}")

if __name__ == '__main__':
    unittest.main()
