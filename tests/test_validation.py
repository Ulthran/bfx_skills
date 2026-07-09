from bfx_mcp.validation import tools as validation


def test_full_guide_covers_all_three_file_types():
    text = validation.get_output_validation_guide()
    for file_type in ("fastq", "bam", "slurm_job"):
        assert file_type in text.lower()


def test_fastq_section_has_fastp_thresholds():
    text = validation.get_output_validation_guide("fastq")
    assert text.startswith("## fastq")
    assert "duplication" in text.lower()
    assert "bam" not in text.split("\n", 1)[0].lower()


def test_bam_section_distinguishes_stool_from_biopsy():
    text = validation.get_output_validation_guide("bam")
    assert text.startswith("## bam")
    assert "stool" in text.lower()
    assert "biopsy" in text.lower()


def test_slurm_job_section_has_seff_guidance():
    text = validation.get_output_validation_guide("slurm_job")
    assert text.startswith("## slurm_job")
    assert "seff" in text.lower()


def test_unknown_file_type_falls_back_gracefully():
    text = validation.get_output_validation_guide("vcf")
    assert "No validation guidance found" in text
