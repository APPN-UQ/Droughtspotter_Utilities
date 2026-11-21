library(tidyverse)
library(patchwork)
library(mgcv)
library(gstat)
library(sp)
library(plyr)


# This is the raw dataset 
september_sample <- read.csv("R:/APPF_Data-Q6940/2025_ThermalVariance_I_Dansmith_/GattonLysimetryFacility_F/ThermalVarianceTripod/2025-10-10/run00/T0_raw/2025-10-13-09-18-06_Thermal variance points_LPad/2025-10-13-09-18-06_Thermal variance points_LPad_database.csv") %>%
  filter(trait %in% c("Av_Temp_0900","PAR_0900","PAR_1200","Av_Temp_1200","PAR_1500","Av_Temp_1500")) %>%
  dplyr::select('Row','Column', 'trait','value','timestamp') %>%
  mutate(Plot_ID = paste(Row, Column, sep="_")) %>%
  unique()


samples_9am <- september_sample %>%
  filter(trait %in% c('Av_Temp_0900','PAR_0900'))


# This is the dataset that Edward cleaned, but removed timestamp
september_sample_clean <- read.csv("R:/APPF_Data-Q6940/2025_ThermalVariance_I_Dansmith_/GattonLysimetryFacility_F/ThermalVarianceTripod/2025-10-10/run00/T1_proc/2025-10-10-11-07-28_Thermal variance points_LPad_table.csv") %>%
  dplyr::select(Row, Column, PAR_1200:Av_Temp_1500) %>%
  mutate(Plot_ID = paste(Row, Column, sep="_")) %>%
  pivot_longer(PAR_1200:Av_Temp_1500, names_to = 'trait') %>%
  unique()


# We update the raw dataset with Ed's clean dataset and include timestamp
september_sample_updated <- september_sample %>% filter(trait %in% c("PAR_1200","Av_Temp_1200","PAR_1500","Av_Temp_1500")) %>%
  rows_update(
    september_sample_clean,
    by = c("Row", "Column", "trait"),
    unmatched = "ignore"
  )

september_sample_updated <- 
  bind_rows(samples_9am, september_sample_updated)

september_sample_updated %>% 
  unique() %>%
  ggplot(aes(x=Column,y=Row)) + 
  geom_tile() +
  geom_label(aes(label=Plot_ID))


# Simple layout

september_sample_updated %>%
  dplyr::select(Row, Column) %>%
  unique() %>%
  ggplot(aes(x=Column,y=
               Row)) + 
  geom_tile(color='black',fill='white') +
  geom_text(aes(label = paste(Row,Column,sep="_")))


library(matlab)

temp <- 
  september_sample_updated %>%
  filter(trait %in% c('Av_Temp_0900','Av_Temp_1200','Av_Temp_1500')) %>%
  filter(value < 40) %>%
  ggplot(aes(x = Column, y = Row)) +
  geom_tile(aes(fill = value)) +
  facet_wrap(~trait, scales = 'free') +
  scale_fill_gradientn(colours = parula(120))  # exact MATLAB parula

temp

# 12:00 PAR
PAR <- 
  september_sample_updated %>%
  filter(trait %in% c('PAR_0900','PAR_1200','PAR_1500')) %>%
  ggplot(aes(x=Column,y=Row)) + geom_tile(aes(fill=value)) + 
  facet_wrap(~trait, scales='free') +
  
  scale_fill_viridis_c() 

PAR


# calculate Row means and standard deviations
RowMeans <- 
  september_sample_updated %>%
  filter(!trait %in%)
  group_by(Row, trait) %>%
  summarise(mean = mean(value), 
            sd = sd(value))

RowMeans %>% ggplot(aes(x=Row,y=mean)) + 
  geom_point() + geom_line(linetype='dashed') + 
  geom_pointrange(aes(ymin=mean-sd/2,ymax=mean+sd/2))+
  facet_wrap(~trait, scales='free')


# Calculate COlumn mneans and standard deviations
ColMeans <- 
  september_sample_updated %>%
  filter(value < 50) %>%
  group_by(Column, trait) %>%
  summarise(mean = mean(value), 
            sd = sd(value))

ColMeans %>% ggplot(aes(x=Column,y=mean)) + 
  geom_point() + geom_line(linetype='dashed') + 
  geom_pointrange(aes(ymin=mean-sd/2,ymax=mean+sd/2))+
  facet_wrap(~trait, scales='free')



# Gam to model x,y variance
gam_PAR_1500 <- gam(value ~ s(Row, Column, k = 20), data = september_sample_updated %>% filter(trait == 'PAR_1500'))
resid_gam_PAR_1500 <- resid(gam_PAR_1500)

# Take the subset used in the fit and add residuals as a column
par1500_dat <- september_sample_updated %>%
  filter(trait == "PAR_1500") %>%
  mutate(resid_gam = resid(gam_PAR_1500))

coordinates(par1500_dat) <- ~ Row + Column

september_sample_updated <- september_sample_updated %>%
  mutate(
    Row    = as.numeric(Row),
    Column = as.numeric(Column)
  )
vgm_PAR1500_emp <- variogram(resid_gam ~ 1, par1500_dat)

plot(vgm_PAR1500_emp)


vgm_PAR1500_dir <- variogram(
  resid_gam ~ 1,
  par1500_dat,
  alpha = c(0, 45, 90, 135)
)

plot(vgm_PAR1500_dir)

vgm_PAR1500_model <- fit.variogram(
  vgm_PAR1500_emp,
  vgm(psill = 1, model = "Exp", range = 3, nugget = 0.1)
)

plot(vgm_PAR1500_emp, vgm_PAR1500_model)
