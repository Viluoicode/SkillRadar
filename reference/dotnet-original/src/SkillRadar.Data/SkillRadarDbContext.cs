using Microsoft.EntityFrameworkCore;
using SkillRadar.Core.Entities;

namespace SkillRadar.Data;

public class SkillRadarDbContext(DbContextOptions<SkillRadarDbContext> options) : DbContext(options)
{
    // Bronze
    public DbSet<RawJobPosting> RawJobPostings => Set<RawJobPosting>();

    // Silver
    public DbSet<Job> Jobs => Set<Job>();

    // Gold
    public DbSet<Skill> Skills => Set<Skill>();
    public DbSet<SkillAlias> SkillAliases => Set<SkillAlias>();
    public DbSet<JobSkill> JobSkills => Set<JobSkill>();
    public DbSet<Role> Roles => Set<Role>();
    public DbSet<SkillDemand> SkillDemands => Set<SkillDemand>();

    // Meta
    public DbSet<IngestionRun> IngestionRuns => Set<IngestionRun>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<RawJobPosting>(e =>
        {
            e.ToTable("raw_job_postings");
            e.HasKey(x => x.Id);
            e.Property(x => x.BoardToken).HasMaxLength(200).IsRequired();
            e.Property(x => x.SourceJobId).HasMaxLength(200).IsRequired();
            e.Property(x => x.RawJson).HasColumnType("jsonb").IsRequired();
            e.HasIndex(x => new { x.Source, x.SourceJobId });
            e.HasIndex(x => x.IngestionRunId);
        });

        b.Entity<Job>(e =>
        {
            e.ToTable("jobs");
            e.HasKey(x => x.Id);
            e.Property(x => x.BoardToken).HasMaxLength(200).IsRequired();
            e.Property(x => x.Company).HasMaxLength(300).IsRequired();
            e.Property(x => x.Title).HasMaxLength(500).IsRequired();
            e.Property(x => x.Location).HasMaxLength(300);
            e.Property(x => x.ApplyUrl).HasMaxLength(1000).IsRequired();
            e.Property(x => x.DedupHash).HasMaxLength(64).IsRequired();
            // Primary dedup key: a posting is unique within its source by native id.
            e.HasIndex(x => new { x.Source, x.SourceJobId }).IsUnique();
            // Cross-source fallback lookups + active-jobs filtering.
            e.HasIndex(x => x.DedupHash);
            e.HasIndex(x => x.IsActive);
            e.HasIndex(x => new { x.Source, x.BoardToken });
        });

        b.Entity<Skill>(e =>
        {
            e.ToTable("skills");
            e.HasKey(x => x.Id);
            e.Property(x => x.Name).HasMaxLength(120).IsRequired();
            e.Property(x => x.Category).HasMaxLength(80).IsRequired();
            e.HasIndex(x => x.Name).IsUnique();
        });

        b.Entity<SkillAlias>(e =>
        {
            e.ToTable("skill_aliases");
            e.HasKey(x => x.Id);
            e.Property(x => x.Alias).HasMaxLength(120).IsRequired();
            e.HasOne(x => x.Skill).WithMany(s => s.Aliases).HasForeignKey(x => x.SkillId)
                .OnDelete(DeleteBehavior.Cascade);
            e.HasIndex(x => x.Alias).IsUnique();
        });

        b.Entity<JobSkill>(e =>
        {
            e.ToTable("job_skills");
            e.HasKey(x => new { x.JobId, x.SkillId });
            e.HasOne(x => x.Job).WithMany(j => j.JobSkills).HasForeignKey(x => x.JobId)
                .OnDelete(DeleteBehavior.Cascade);
            e.HasOne(x => x.Skill).WithMany(s => s.JobSkills).HasForeignKey(x => x.SkillId)
                .OnDelete(DeleteBehavior.Cascade);
            e.HasIndex(x => x.SkillId);
        });

        b.Entity<Role>(e =>
        {
            e.ToTable("roles");
            e.HasKey(x => x.Id);
            e.Property(x => x.Name).HasMaxLength(120).IsRequired();
            e.Property(x => x.TitlePatterns).HasColumnType("text[]");
            e.HasIndex(x => x.Name).IsUnique();
        });

        b.Entity<SkillDemand>(e =>
        {
            e.ToTable("skill_demand");
            e.HasKey(x => x.Id);
            e.HasOne(x => x.Role).WithMany().HasForeignKey(x => x.RoleId)
                .OnDelete(DeleteBehavior.Cascade);
            e.HasOne(x => x.Skill).WithMany().HasForeignKey(x => x.SkillId)
                .OnDelete(DeleteBehavior.Cascade);
            e.HasIndex(x => new { x.RoleId, x.SnapshotDate, x.SkillId }).IsUnique();
        });

        b.Entity<IngestionRun>(e =>
        {
            e.ToTable("ingestion_runs");
            e.HasKey(x => x.Id);
            e.Property(x => x.Trigger).HasMaxLength(40).IsRequired();
            e.HasIndex(x => x.StartedAt);
        });
    }
}
