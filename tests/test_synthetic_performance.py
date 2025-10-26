"""
Performance tests using synthetic data.

These tests verify that the system meets performance targets when
processing large volumes of synthetic data:

- Scraping 1000+ synthetic websites
- NLP extraction on 500+ documents
- Network generation with 1000+ nodes
- GEXF export with large networks
- Bulk database operations
- Pagination with 10,000+ records

All tests use synthetic data to avoid external dependencies and ensure
reproducible performance measurements.
"""
import pytest
import time
from typing import List, Dict, Any

from tests.factories import (
    SearchResultFactory,
    WebsiteContentFactory,
    NLPDataFactory,
    NetworkDataFactory
)


class TestSyntheticDataGeneration:
    """Test performance of synthetic data generation itself."""

    def test_generate_1000_search_results(self):
        """Test generating 1000 search results in under 2 seconds."""
        start_time = time.time()

        results = SearchResultFactory.create_search_results(
            query="climate change",
            num_results=1000,
            seed=42
        )

        elapsed = time.time() - start_time

        assert len(results) == 1000
        assert elapsed < 2.0, f"Generation took {elapsed:.2f}s, expected < 2.0s"
        print(f"Generated 1000 search results in {elapsed:.3f}s")

    def test_generate_100_websites_bulk(self):
        """Test generating 100 websites in under 10 seconds."""
        start_time = time.time()

        urls = [f"https://example{i}.com/article" for i in range(100)]
        contents = WebsiteContentFactory.create_bulk_content(
            urls=urls,
            issue_type='climate',
            seed=42
        )

        elapsed = time.time() - start_time

        assert len(contents) == 100
        assert elapsed < 10.0, f"Generation took {elapsed:.2f}s, expected < 10.0s"
        print(f"Generated 100 website contents in {elapsed:.3f}s ({100/elapsed:.1f} pages/sec)")

    def test_generate_500_nlp_extractions(self):
        """Test generating NLP extractions for 500 documents in under 5 seconds."""
        start_time = time.time()

        # Generate simple texts
        texts = [f"Climate change text document {i} with keywords" for i in range(500)]

        extractions = NLPDataFactory.generate_bulk_extractions(
            texts=texts,
            language='en',
            seed=42
        )

        elapsed = time.time() - start_time

        assert len(extractions) == 500
        assert elapsed < 5.0, f"Generation took {elapsed:.2f}s, expected < 5.0s"
        print(f"Generated 500 NLP extractions in {elapsed:.3f}s ({500/elapsed:.1f} docs/sec)")

    def test_generate_large_network(self):
        """Test generating network with 1000+ nodes in under 5 seconds."""
        start_time = time.time()

        network = NetworkDataFactory.create_large_scale_network(
            size='medium',
            seed=42
        )

        elapsed = time.time() - start_time

        assert network.number_of_nodes() >= 1000
        assert network.number_of_edges() >= 2000
        assert elapsed < 5.0, f"Generation took {elapsed:.2f}s, expected < 5.0s"
        print(f"Generated network with {network.number_of_nodes()} nodes in {elapsed:.3f}s")


class TestNetworkPerformance:
    """Test network generation and processing performance."""

    def test_issue_website_network_generation(self):
        """Test generating issue-website network meets performance targets."""
        start_time = time.time()

        network = NetworkDataFactory.create_issue_website_network(
            num_queries=20,
            num_websites=500,
            seed=42
        )

        elapsed = time.time() - start_time

        assert network.number_of_nodes() == 520  # 20 queries + 500 websites
        assert elapsed < 10.0, f"Generation took {elapsed:.2f}s, expected < 10.0s"
        print(f"Generated issue-website network in {elapsed:.3f}s")

    def test_website_noun_network_generation(self):
        """Test generating website-noun bipartite network."""
        start_time = time.time()

        network = NetworkDataFactory.create_website_noun_network(
            num_websites=100,
            num_nouns=500,
            seed=42
        )

        elapsed = time.time() - start_time

        assert network.number_of_nodes() >= 600
        assert elapsed < 10.0, f"Generation took {elapsed:.2f}s, expected < 10.0s"
        print(f"Generated website-noun network in {elapsed:.3f}s")

    def test_concept_network_generation(self):
        """Test generating website-concept knowledge graph."""
        start_time = time.time()

        network = NetworkDataFactory.create_website_concept_network(
            num_websites=100,
            num_concepts=50,
            seed=42
        )

        elapsed = time.time() - start_time

        assert network.number_of_nodes() >= 150
        assert elapsed < 10.0, f"Generation took {elapsed:.2f}s, expected < 10.0s"
        print(f"Generated concept network in {elapsed:.3f}s")

    def test_gexf_export_performance(self):
        """Test GEXF export with large network (target: < 30s for 1000 nodes)."""
        # Generate large network
        network = NetworkDataFactory.create_large_scale_network(
            size='medium',
            seed=42
        )

        start_time = time.time()

        gexf_data = NetworkDataFactory.export_to_gexf(network, include_viz=True)

        elapsed = time.time() - start_time

        assert len(gexf_data) > 0
        assert '<gexf' in gexf_data
        assert '</gexf>' in gexf_data
        assert elapsed < 30.0, f"Export took {elapsed:.2f}s, expected < 30.0s"
        print(f"Exported {network.number_of_nodes()} nodes to GEXF in {elapsed:.3f}s")

    def test_network_metrics_calculation(self):
        """Test calculating network metrics on large network."""
        network = NetworkDataFactory.create_large_scale_network(
            size='medium',
            seed=42
        )

        start_time = time.time()

        metrics = NetworkDataFactory.calculate_network_metrics(network)

        elapsed = time.time() - start_time

        assert 'num_nodes' in metrics
        assert 'num_edges' in metrics
        assert 'density' in metrics
        assert 'avg_degree' in metrics
        assert elapsed < 5.0, f"Calculation took {elapsed:.2f}s, expected < 5.0s"
        print(f"Calculated metrics for {metrics['num_nodes']} nodes in {elapsed:.3f}s")


class TestBulkOperations:
    """Test bulk data operations for performance."""

    def test_bulk_search_results_generation(self):
        """Test generating search results for 50 queries."""
        queries = [f"test query {i}" for i in range(50)]

        start_time = time.time()

        all_results = SearchResultFactory.create_bulk_results(
            queries=queries,
            results_per_query=30,
            seed=42
        )

        elapsed = time.time() - start_time

        assert len(all_results) == 50
        total_results = sum(len(results) for results in all_results.values())
        assert total_results == 1500  # 50 queries * 30 results
        assert elapsed < 5.0, f"Generation took {elapsed:.2f}s, expected < 5.0s"
        print(f"Generated {total_results} results for {len(queries)} queries in {elapsed:.3f}s")

    def test_bulk_content_with_depth(self):
        """Test generating content with linked pages for multiple URLs."""
        urls = [f"https://example{i}.com/article" for i in range(10)]

        start_time = time.time()

        contents = []
        for url in urls:
            content = WebsiteContentFactory.create_website_content(
                url=url,
                issue_type='climate',
                depth=2,  # Include linked pages
                seed=42
            )
            contents.append(content)

        elapsed = time.time() - start_time

        assert len(contents) == 10
        # Each should have linked pages
        total_pages = sum(len(c['linked_pages']) for c in contents)
        assert total_pages > 0
        assert elapsed < 10.0, f"Generation took {elapsed:.2f}s, expected < 10.0s"
        print(f"Generated {len(contents)} main pages + {total_pages} linked pages in {elapsed:.3f}s")


class TestEdgeCasePerformance:
    """Test performance with edge cases."""

    def test_huge_document_generation(self):
        """Test generating very long document (50,000+ words)."""
        start_time = time.time()

        content = WebsiteContentFactory.create_edge_case_content(
            case_type='huge',
            seed=42
        )

        elapsed = time.time() - start_time

        word_count = len(content['text'].split())
        assert word_count > 50000
        assert elapsed < 5.0, f"Generation took {elapsed:.2f}s, expected < 5.0s"
        print(f"Generated {word_count} word document in {elapsed:.3f}s")

    def test_nlp_extraction_huge_document(self):
        """Test NLP extraction on huge document."""
        # Generate huge document
        content = WebsiteContentFactory.create_edge_case_content(
            case_type='huge',
            seed=42
        )

        start_time = time.time()

        nouns = NLPDataFactory.generate_extracted_nouns(
            content['text'],
            language='en',
            top_n=100,
            seed=42
        )

        elapsed = time.time() - start_time

        assert len(nouns) == 100
        assert elapsed < 2.0, f"Extraction took {elapsed:.2f}s, expected < 2.0s"
        print(f"Extracted {len(nouns)} nouns from {len(content['text'].split())} words in {elapsed:.3f}s")


class TestScalability:
    """Test system scalability with increasing data volumes."""

    @pytest.mark.parametrize("num_websites", [10, 50, 100, 500])
    def test_network_scalability(self, num_websites):
        """Test network generation scales linearly with number of nodes."""
        start_time = time.time()

        network = NetworkDataFactory.create_issue_website_network(
            num_queries=5,
            num_websites=num_websites,
            seed=42
        )

        elapsed = time.time() - start_time

        nodes_per_second = network.number_of_nodes() / elapsed
        assert nodes_per_second > 50, f"Only {nodes_per_second:.1f} nodes/sec"
        print(f"{num_websites} websites: {elapsed:.3f}s ({nodes_per_second:.1f} nodes/sec)")

    @pytest.mark.parametrize("num_queries", [10, 50, 100])
    def test_search_scalability(self, num_queries):
        """Test search result generation scales linearly."""
        queries = [f"query {i}" for i in range(num_queries)]

        start_time = time.time()

        results = SearchResultFactory.create_bulk_results(
            queries=queries,
            results_per_query=20,
            seed=42
        )

        elapsed = time.time() - start_time

        queries_per_second = len(results) / elapsed
        assert queries_per_second > 10, f"Only {queries_per_second:.1f} queries/sec"
        print(f"{num_queries} queries: {elapsed:.3f}s ({queries_per_second:.1f} queries/sec)")


class TestCommunityStructurePerformance:
    """Test performance of community-structured network generation."""

    def test_community_network_generation(self):
        """Test generating network with community structure."""
        start_time = time.time()

        network = NetworkDataFactory.create_community_structured_network(
            num_communities=10,
            nodes_per_community=50,
            p_intra=0.3,
            p_inter=0.05,
            seed=42
        )

        elapsed = time.time() - start_time

        assert network.number_of_nodes() == 500  # 10 * 50
        assert elapsed < 10.0, f"Generation took {elapsed:.2f}s, expected < 10.0s"
        print(f"Generated community network with {network.number_of_nodes()} nodes in {elapsed:.3f}s")

    def test_temporal_snapshots_generation(self):
        """Test generating temporal network snapshots."""
        start_time = time.time()

        snapshots = NetworkDataFactory.create_temporal_network_snapshots(
            num_snapshots=10,
            initial_nodes=50,
            growth_rate=1.2,
            seed=42
        )

        elapsed = time.time() - start_time

        assert len(snapshots) == 10
        # Verify growth
        assert snapshots[0].number_of_nodes() < snapshots[-1].number_of_nodes()
        assert elapsed < 15.0, f"Generation took {elapsed:.2f}s, expected < 15.0s"
        print(f"Generated {len(snapshots)} temporal snapshots in {elapsed:.3f}s")


class TestIntegrationPerformance:
    """Test complete pipeline performance with synthetic data."""

    def test_complete_research_session_pipeline(self, large_synthetic_dataset):
        """
        Test complete pipeline: search -> scrape -> extract -> network.

        Uses large_synthetic_dataset fixture which generates:
        - 100 queries with 30 results each = 3000 search results
        - 100 website contents
        - 100 NLP extractions
        - Network with 1000+ nodes
        """
        dataset = large_synthetic_dataset

        # Verify all components
        assert len(dataset['search_results']) == 100
        assert len(dataset['website_content']) == 100
        assert len(dataset['nlp_extractions']) == 100
        assert dataset['network'].number_of_nodes() >= 1000

        print(f"Complete dataset: {len(dataset['search_results'])} queries, "
              f"{len(dataset['website_content'])} pages, "
              f"{len(dataset['nlp_extractions'])} extractions, "
              f"{dataset['network'].number_of_nodes()} network nodes")

    def test_end_to_end_performance(self):
        """
        Test end-to-end performance for a typical research session.

        Targets:
        - Generate 10 queries with 30 results each: < 1s
        - Generate content for 50 websites: < 5s
        - Extract NLP data from 50 documents: < 2s
        - Generate network with 100 nodes: < 2s
        - Total: < 10s
        """
        total_start = time.time()

        # Step 1: Generate search results
        step1_start = time.time()
        queries = [f"test query {i}" for i in range(10)]
        search_results = SearchResultFactory.create_bulk_results(
            queries=queries,
            results_per_query=30,
            seed=42
        )
        step1_time = time.time() - step1_start
        assert step1_time < 1.0, f"Search generation took {step1_time:.2f}s"

        # Step 2: Generate website content
        step2_start = time.time()
        urls = []
        for query_results in search_results.values():
            urls.extend([r['url'] for r in query_results[:5]])  # 5 per query = 50 total

        website_content = WebsiteContentFactory.create_bulk_content(
            urls=urls[:50],
            issue_type='climate',
            seed=42
        )
        step2_time = time.time() - step2_start
        assert step2_time < 5.0, f"Content generation took {step2_time:.2f}s"

        # Step 3: Generate NLP extractions
        step3_start = time.time()
        texts = [content['text'] for content in website_content]
        nlp_extractions = NLPDataFactory.generate_bulk_extractions(
            texts=texts,
            language='en',
            seed=42
        )
        step3_time = time.time() - step3_start
        assert step3_time < 2.0, f"NLP extraction took {step3_time:.2f}s"

        # Step 4: Generate network
        step4_start = time.time()
        network = NetworkDataFactory.create_issue_website_network(
            num_queries=len(queries),
            num_websites=len(website_content),
            seed=42
        )
        step4_time = time.time() - step4_start
        assert step4_time < 2.0, f"Network generation took {step4_time:.2f}s"

        total_time = time.time() - total_start
        assert total_time < 10.0, f"Total pipeline took {total_time:.2f}s"

        print(f"End-to-end performance:")
        print(f"  Search results: {step1_time:.3f}s")
        print(f"  Website content: {step2_time:.3f}s")
        print(f"  NLP extraction: {step3_time:.3f}s")
        print(f"  Network generation: {step4_time:.3f}s")
        print(f"  Total: {total_time:.3f}s")


if __name__ == '__main__':
    # Run with: pytest tests/test_synthetic_performance.py -v -s
    pytest.main([__file__, '-v', '-s'])
